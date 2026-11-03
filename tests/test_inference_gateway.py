import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

SCRIPT=Path(__file__).parents[1]/'tools/inference_gateway.py'


class Response(io.BytesIO):
    status=200
    def __init__(self,data,content_type='application/json'):
        super().__init__(data);self.headers={'Content-Type':content_type}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(),'Gateway implementation is missing')
        spec=importlib.util.spec_from_file_location('gateway',SCRIPT)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.now=[time.time()]
        self.config={'lease_id':'fixture-lease','deadline':self.now[0]+3600,'quota_usd':'0.05','model':'fixture-model','upstream':'https://api.runpod.ai/v2/fixture/openai/v1','input_price_per_million':'0.77','output_price_per_million':'2.42','max_tokens':4096,'max_body_bytes':16384,'state_file':str(root/'usage.json')}
        self.calls=[]
        def transport(body):
            self.calls.append(body)
            return Response(json.dumps({'choices':[{'message':{'role':'assistant','content':'pwd'}}],'usage':{'prompt_tokens':10,'completion_tokens':3}}).encode())
        self.transport=transport
        self.start_server()

    def start_server(self):
        self.server=self.m.GatewayServer(('127.0.0.1',0),self.config,'fixture-client-token',lambda body:self.transport(body),clock=lambda:self.now[0])
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.url='http://127.0.0.1:'+str(self.server.server_port)

    def request(self,path='/v1/chat/completions',body=None,auth=True,request_id=None):
        headers={}
        if auth:headers['Authorization']='Bearer fixture-client-token'
        if request_id:headers['Idempotency-Key']=request_id
        data=None if body is None else json.dumps(body).encode()
        req=urllib.request.Request(self.url+path,data=data,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=3) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as error:return error.code,error.read(),error.headers

    def payload(self,**extra):
        return {'model':'fixture-model','messages':[{'role':'user','content':'Harmless command help'}],'max_tokens':128,**extra}

    def test_authentication_precedes_any_upstream_or_budget_use(self):
        self.assertEqual(self.request('/v1/models',auth=False)[0],401)
        self.assertEqual(self.request(body=self.payload(),auth=False)[0],401)
        status,body,_=self.request('/v1/models')
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['data'][0]['id'],'fixture-model')
        self.assertEqual(self.calls,[])

    def test_tool_schema_and_tool_role_are_preserved(self):
        body=self.payload(tools=[{'type':'function','function':{'name':'directory','parameters':{'type':'object','properties':{}}}}])
        body['messages']=[{'role':'assistant','content':None,'tool_calls':[{'id':'call-1','type':'function','function':{'name':'directory','arguments':'{}'}}]},{'role':'tool','tool_call_id':'call-1','content':'/synthetic/demo'}]
        status,result,_=self.request(body=body)
        self.assertEqual(status,200);self.assertEqual(json.loads(result)['choices'][0]['message']['content'],'pwd')
        self.assertEqual(self.calls,[body])

    def test_expiry_and_quota_deny_before_upstream(self):
        self.now[0]=self.config['deadline']+1
        self.assertEqual(self.request(body=self.payload())[0],410);self.assertEqual(self.calls,[])
        self.now[0]=self.config['deadline']-100
        self.server.budget.config['quota_usd']='0.001'
        self.assertEqual(self.request(body=self.payload())[0],402);self.assertEqual(self.calls,[])

    def test_ambiguous_failure_is_reserved_and_never_automatically_retried(self):
        def fail(body):self.calls.append(body);raise TimeoutError('synthetic transport timeout')
        self.transport=fail
        status,_,_=self.request(body=self.payload(),request_id='unique-request')
        self.assertEqual(status,504);self.assertEqual(len(self.calls),1)
        self.assertEqual(self.request(body=self.payload(),request_id='unique-request')[0],409)
        self.assertEqual(len(self.calls),1)
        state=json.loads(Path(self.config['state_file']).read_text())
        self.assertGreater(float(state['reserved_usd']),0)
        self.assertNotIn('Harmless command help',json.dumps(state))

    def test_oversized_or_unbounded_options_do_not_dispatch(self):
        for body in (self.payload(n=2),self.payload(max_tokens=999999),self.payload(model='other-model'),self.payload(unknown_vendor_option=True),self.payload(messages=[{'role':'user','content':'x'*20000}])):
            self.assertIn(self.request(body=body)[0],(400,413))
        self.assertEqual(self.calls,[])

    def test_health_expires_without_generating_on_poll(self):
        status,body,_=self.request('/health')
        self.assertEqual(status,200);self.assertFalse(json.loads(body)['inference_fresh'])
        self.assertEqual(self.calls,[])
        self.assertEqual(self.request(body=self.payload())[0],200)
        self.assertTrue(json.loads(self.request('/health')[1])['inference_fresh'])
        self.now[0]+=301
        self.assertFalse(json.loads(self.request('/health')[1])['inference_fresh'])
        self.assertEqual(len(self.calls),1)

    def test_sse_format_is_forwarded_and_request_replay_is_durable(self):
        stream=b'data: {"choices":[{"delta":{"content":"pwd"}}]}\n\ndata: [DONE]\n\n'
        self.transport=lambda body:Response(stream,'text/event-stream')
        status,body,headers=self.request(body=self.payload(stream=True),request_id='stream-request')
        self.assertEqual(status,200);self.assertEqual(body,stream)
        self.assertIn('text/event-stream',headers['Content-Type'])
        budget=self.m.Budget(self.config,clock=lambda:self.now[0])
        with self.assertRaises(self.m.AdmissionError) as error:budget.reserve('stream-request',100,128)
        self.assertEqual(error.exception.status,409)
        changed={**self.config,'deadline':self.config['deadline']+1}
        with self.assertRaises(ValueError):self.m.Budget(changed,clock=lambda:self.now[0])

    def test_invalid_json_is_a_client_error_without_dispatch(self):
        req=urllib.request.Request(self.url+'/v1/chat/completions',data=b'{',headers={'Authorization':'Bearer fixture-client-token'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req,timeout=3)
        self.assertEqual(error.exception.code,400);self.assertEqual(self.calls,[])

    def test_provider_http_status_is_reported_without_secret_body_or_retry(self):
        def fail(body):
            self.calls.append(body)
            raise urllib.error.HTTPError('https://api.runpod.ai/v2/fixture/openai/v1/chat/completions',403,'denied',{},None)
        self.transport=fail
        status,body,_=self.request(body=self.payload())
        self.assertEqual(status,502);self.assertIn('403',body.decode());self.assertEqual(len(self.calls),1)

    def test_interrupted_stream_does_not_claim_fresh_inference(self):
        class Broken(Response):
            def read1(self,limit):
                if not hasattr(self,'sent'):
                    self.sent=True;return b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                raise TimeoutError('interrupted synthetic stream')
        self.transport=lambda body:Broken(b'','text/event-stream')
        self.request(body=self.payload(stream=True))
        self.assertFalse(json.loads(self.request('/health')[1])['inference_fresh'])

    def test_expiry_between_admission_and_dispatch_does_not_call_provider(self):
        original=self.server.budget.reserve
        def reserve(*args):
            result=original(*args);self.now[0]=self.config['deadline']+1;return result
        self.server.budget.reserve=reserve
        status,_,_=self.request(body=self.payload())
        self.assertEqual(status,410);self.assertEqual(self.calls,[])

    def test_secret_validation_does_not_echo_malformed_value(self):
        path=Path(self.tmp.name)/'bad-secret';path.write_text('synthetic\nmultiline-secret');path.chmod(0o600)
        with self.assertRaises(ValueError) as error:self.m.secret_file(path)
        self.assertNotIn('multiline-secret',str(error.exception))

    def test_malformed_nested_fields_and_nonfinite_numbers_never_reserve_or_dispatch(self):
        malformed=[self.payload(tools='not-an-array'),self.payload(temperature={'bad':'shape'}),
          self.payload(temperature=float('nan')),self.payload(top_p=float('inf')),
          self.payload(messages=[{'role':'user','content':'hello','unknown':'field'}]),
          self.payload(messages=[{'role':'assistant','content':None,'tool_calls':'not-an-array'}]),
          self.payload(messages=[{'role':'tool','content':'result'}]),
          self.payload(tools=[{'type':'function','function':{'name':'bad','parameters':{'default':float('inf')}}}]),
          self.payload(stream_options={'include_usage':'yes'}),self.payload(seed=True),
          self.payload(tools=[{'type':'function','function':{'name':'directory'}}],tool_choice={'type':'function','function':{'name':[]}}),
          self.payload(response_format={'type':'json_schema','json_schema':{'name':'answer','schema':{},'description':17}})]
        for payload in malformed:
            with self.subTest(payload=payload):self.assertEqual(self.request(body=payload)[0],400)
        self.assertEqual(self.calls,[])
        state=json.loads(Path(self.config['state_file']).read_text());self.assertEqual(state['reserved_usd'],'0')

    def test_valid_tool_argument_strings_are_opaque_and_preserved(self):
        body=self.payload(messages=[{'role':'assistant','content':None,'tool_calls':[{'id':'call-1','type':'function','function':{'name':'directory','arguments':'opaque, not parsed as JSON'}}]},{'role':'tool','tool_call_id':'call-1','content':'synthetic'}])
        self.assertEqual(self.request(body=body)[0],200);self.assertEqual(self.calls,[body])

    def test_deadline_crossed_during_stream_read_does_not_forward_or_succeed(self):
        outer=self
        class Late(Response):
            def read1(self,limit):
                if not hasattr(self,'sent'):
                    self.sent=True;outer.now[0]=outer.config['deadline']+1
                    return b'data: {"choices":[{"delta":{"content":"late-content"}}]}\n\ndata: [DONE]\n\n'
                return b''
        self.transport=lambda body:Late(b'','text/event-stream')
        _,body,_=self.request(body=self.payload(stream=True),request_id='late-stream')
        self.assertNotIn(b'late-content',body)
        state=json.loads(Path(self.config['state_file']).read_text())
        self.assertNotEqual(state['requests']['late-stream']['outcome'],'completed')

    def test_malformed_and_error_provider_choices_never_refresh_readiness(self):
        variants=[{'choices':'not-a-list'}, {'choices':[{'message':'not-an-object'}]},
                  {'error':{'message':'synthetic error'},'choices':[{'message':{'role':'assistant','content':'pwd'}}]}]
        for response in variants:
            self.transport=lambda body,response=response:Response(json.dumps(response).encode())
            self.assertEqual(self.request(body=self.payload())[0],502)
            self.assertFalse(json.loads(self.request('/health')[1])['inference_fresh'])
        self.transport=lambda body:Response(b'data: {"choices":"invalid"}\n\ndata: [DONE]\n\n','text/event-stream')
        self.request(body=self.payload(stream=True))
        self.assertFalse(json.loads(self.request('/health')[1])['inference_fresh'])

    def test_actual_rootshell_custom_ceiling_and_large_valid_body_are_preserved(self):
        self.server.shutdown();self.server.server_close()
        self.config={**self.config,'max_tokens':44096,'max_body_bytes':65536,'quota_usd':'1','state_file':str(Path(self.tmp.name)/'native-usage.json')}
        self.start_server()
        body=self.payload(max_tokens=44096,messages=[{'role':'user','content':'x'*60000}])
        self.assertEqual(self.request(body=body)[0],200)
        self.assertEqual(self.calls,[body])

    def test_nullable_standard_tool_stream_fragments_are_preserved(self):
        stream=b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":null,"type":null,"function":{"arguments":null}}]}}]}\n\ndata: [DONE]\n\n'
        self.transport=lambda body:Response(stream,'text/event-stream')
        status,body,_=self.request(body=self.payload(stream=True))
        self.assertEqual(status,200);self.assertEqual(body,stream)
        self.assertTrue(json.loads(self.request('/health')[1])['inference_fresh'])


if __name__=='__main__':unittest.main()
