#!/usr/bin/env python3
"""Bounded text-only Runpod transport. No shell, conversation store, or paid retries."""
import argparse
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
import fcntl
import hashlib
import hmac
import http.client
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class AdmissionError(Exception):
    def __init__(self,status,message):
        super().__init__(message);self.status=status


def money(value):
    number=Decimal(str(value))
    if not number.is_finite() or number<0:raise ValueError('Invalid nonnegative price/quota')
    return number


def validate_config(config):
    required=('lease_id','deadline','quota_usd','model','upstream','input_price_per_million','output_price_per_million','state_file')
    if any(key not in config for key in required):raise ValueError('Incomplete private configuration')
    url=urllib.parse.urlsplit(config['upstream'])
    if (url.scheme!='https' or url.hostname!='api.runpod.ai' or url.port is not None
            or url.username or url.password or url.query or url.fragment
            or not re.fullmatch(r'/v2/[A-Za-z0-9_-]+/openai/v1',url.path)):
        raise ValueError('Upstream must be one fixed native Runpod OpenAI API root')
    if not math.isfinite(float(config['deadline'])) or float(config['deadline'])<=0:
        raise ValueError('Invalid immutable deadline')
    if not 0<money(config['quota_usd'])<=40:raise ValueError('Invalid lease quota')
    for key in ('input_price_per_million','output_price_per_million'):money(config[key])
    if type(config.get('max_tokens',4096)) is not int or not 1<=config.get('max_tokens',4096)<=65536:
        raise ValueError('Output limit must be 1..65536 tokens')
    if type(config.get('max_body_bytes',16384)) is not int or not 1<=config.get('max_body_bytes',16384)<=65536:
        raise ValueError('Body limit must be 1..65536 bytes')
    if not isinstance(config['model'],str) or not config['model'] or len(config['model'])>200:
        raise ValueError('Invalid model identifier')


def atomic_json(path,value):
    fd,temporary=tempfile.mkstemp(prefix='.admission-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),0o600)
            json.dump(value,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:Path(temporary).unlink(missing_ok=True)


class Budget:
    def __init__(self,config,clock=time.time):
        validate_config(config)
        self.config=dict(config);self.clock=clock;self.path=Path(config['state_file'])
        self.path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
        binding={k:config.get(k) for k in ('lease_id','deadline','quota_usd','model','upstream','input_price_per_million','output_price_per_million','max_tokens','max_body_bytes')}
        self.binding=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
        with self.locked() as state:pass

    @contextmanager
    def locked(self):
        if self.path.is_symlink():raise ValueError('Admission state must not be a symlink')
        fd=os.open(str(self.path)+'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            state=json.loads(self.path.read_text()) if self.path.exists() else {'schema':1,'binding':self.binding,'reserved_usd':'0','requests':{},'last_success':None}
            if state.get('schema')!=1 or state.get('binding')!=self.binding:
                raise ValueError('State belongs to another immutable lease/model/price contract')
            yield state
            atomic_json(self.path,state)
        finally:os.close(fd)

    def reserve(self,request_id,body_bytes,output_tokens):
        with self.locked() as state:
            if self.clock()>=float(self.config['deadline']):raise AdmissionError(410,'Lease expired')
            if request_id in state['requests']:raise AdmissionError(409,'Request identity already admitted; do not retry an ambiguous paid request')
            if any(r['outcome']=='pending' for r in state['requests'].values()):raise AdmissionError(429,'One inference request is already active or awaiting reconciliation')
            # Byte-based bound plus generous template overhead; held reservations are
            # deliberately never refunded, even when returned usage is smaller.
            upper=(money(self.config['input_price_per_million'])*(body_bytes*2+8192)
                   +money(self.config['output_price_per_million'])*output_tokens)/1_000_000
            reserve=max(Decimal('0.01'),(upper*Decimal('1.12')).quantize(Decimal('0.01'),rounding=ROUND_CEILING))
            total=money(state['reserved_usd'])+reserve
            if total>money(self.config['quota_usd']):raise AdmissionError(402,'Conservative inference quota exhausted')
            state['reserved_usd']=str(total)
            state['requests'][request_id]={'reserved_usd':str(reserve),'at':self.clock(),'outcome':'pending'}
        return reserve

    def finish(self,request_id,success,usage=None):
        with self.locked() as state:
            row=state['requests'][request_id]
            row['outcome']='completed' if success else 'uncertain-or-failed'
            row['finished_at']=self.clock()
            if usage:
                row['usage']={k:v for k,v in usage.items() if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and 0<=v<=10_000_000}
            if success:state['last_success']=self.clock()

    def status(self):
        with self.locked() as state:
            active=self.clock()<float(self.config['deadline'])
            fresh=state['last_success'] is not None and 0<=self.clock()-state['last_success']<=300
            return {'service_reachable':True,'client_authorized':True,'model':self.config['model'],
                    'model_supported_cached':True,'lease_active':active,'deadline':self.config['deadline'],
                    'conservative_reserved_usd':state['reserved_usd'],
                    'remaining_quota_usd':str(max(Decimal(0),money(self.config['quota_usd'])-money(state['reserved_usd']))),
                    'last_successful_inference_at':state['last_success'],'inference_fresh':active and fresh}


def secret_file(path):
    path=Path(path)
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise ValueError('Secret file must be private, regular and owned by this user')
    value=path.read_text().strip()
    if not value or not value.isascii() or any(c.isspace() for c in value):raise ValueError('Empty or malformed single-line secret file')
    return value


class NativeResponse:
    def __init__(self,response,connection,sock):
        self.response=response;self.connection=connection;self.sock=sock
        self.status=response.status;self.headers=response.headers;self.timeout=20
    def set_read_timeout(self,timeout):self.timeout=timeout
    def read1(self,limit):
        if self.response.isclosed():return b''
        self.sock.settimeout(self.timeout)
        return self.response.read1(limit)
    def __enter__(self):return self
    def __exit__(self,*args):
        self.response.close();self.connection.close()


def native_transport(config):
    validate_config(config)
    parsed=urllib.parse.urlsplit(config['upstream'])
    def send(body):
        remaining=config['deadline']-time.time()
        if remaining<=0:raise AdmissionError(410,'Lease expired before connection')
        key=secret_file(config['provider_key_file'])
        connection=http.client.HTTPSConnection(parsed.hostname,timeout=min(20,remaining),context=ssl.create_default_context())
        try:
            connection.connect();sock=connection.sock
            remaining=config['deadline']-time.time()
            if remaining<=0:raise AdmissionError(410,'Lease expired before provider dispatch')
            sock.settimeout(min(20,remaining))
            connection.request('POST',parsed.path+'/chat/completions',body=json.dumps(body,allow_nan=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            response=connection.getresponse()
            if response.status!=200:
                status=response.status;response.close()
                raise urllib.error.HTTPError(config['upstream'],status,'Provider rejected request',{},None)
            return NativeResponse(response,connection,sock)
        except BaseException:
            connection.close();raise
    return send


def finite_json(value):
    pending=[(value,0)]
    while pending:
        item,depth=pending.pop()
        if depth>64:raise AdmissionError(400,'JSON nesting exceeds this capability')
        if isinstance(item,float) and not math.isfinite(item):raise AdmissionError(400,'Nonfinite JSON numbers are unsupported')
        if isinstance(item,dict):pending.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list):pending.extend((v,depth+1) for v in item)


def shape(value,keys,message):
    if not isinstance(value,dict) or set(value)-set(keys):raise AdmissionError(400,message)


def name_string(value):
    return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value) is not None


def call_valid(value,delta=False):
    if not isinstance(value,dict):return False
    if delta:
        if type(value.get('index')) is not int or value['index']<0:return False
        if 'id' in value and value['id'] is not None and not isinstance(value['id'],str):return False
        if value.get('type') not in (None,'function'):return False
        function=value.get('function')
        return function is None or isinstance(function,dict) and all(k in ('name','arguments') and (v is None or isinstance(v,str)) for k,v in function.items())
    if set(value)-{'id','type','function'} or not isinstance(value.get('id'),str) or not 1<=len(value['id'])<=200 or value.get('type')!='function':return False
    function=value.get('function')
    return (isinstance(function,dict) and set(function)=={'name','arguments'}
            and name_string(function.get('name')) and isinstance(function.get('arguments'),str))


def answer_valid(message):
    if not isinstance(message,dict) or message.get('role')!='assistant':return False
    content=message.get('content')
    if content is not None and not isinstance(content,str):return False
    calls=message.get('tool_calls')
    if calls is not None and (not isinstance(calls,list) or not calls or not all(call_valid(c) for c in calls)):return False
    return isinstance(content,str) or bool(calls) or isinstance(message.get('refusal'),str)


def choices_valid(value,streaming=False):
    if not isinstance(value,list) or (not streaming and len(value)!=1):return False
    for choice in value:
        if not isinstance(choice,dict):return False
        if 'index' in choice and (type(choice['index']) is not int or choice['index']<0):return False
        if not streaming:
            if not answer_valid(choice.get('message')):return False
        else:
            delta=choice.get('delta')
            if not isinstance(delta,dict):return False
            for key in ('content','reasoning_content','refusal'):
                if key in delta and delta[key] is not None and not isinstance(delta[key],str):return False
            if 'role' in delta and delta['role']!='assistant':return False
            if 'tool_calls' in delta and (not isinstance(delta['tool_calls'],list) or not all(call_valid(c,True) for c in delta['tool_calls'])):return False
    return True


def validate_body(body,config):
    allowed={'model','messages','max_tokens','max_completion_tokens','temperature','top_p','stream','stream_options','stop','tools','tool_choice','parallel_tool_calls','response_format','presence_penalty','frequency_penalty','seed','user','n'}
    if not isinstance(body,dict) or set(body)-allowed:raise AdmissionError(400,'Unsupported request fields')
    if body.get('model')!=config['model']:raise AdmissionError(400,'Only the selected model is allowed')
    finite_json(body)
    messages=body.get('messages')
    if not isinstance(messages,list) or not 1<=len(messages)<=64:raise AdmissionError(400,'Expected 1..64 messages')
    for message in messages:
        if not isinstance(message,dict) or message.get('role') not in ('system','developer','user','assistant','tool'):
            raise AdmissionError(400,'Unsupported message role')
        shape(message,('role','content','name','tool_call_id','tool_calls','refusal','reasoning_content'),'Unsupported message fields')
        if 'name' in message and not name_string(message['name']):raise AdmissionError(400,'Invalid message name')
        if 'tool_call_id' in message and (message['role']!='tool' or not isinstance(message['tool_call_id'],str) or not 1<=len(message['tool_call_id'])<=200):raise AdmissionError(400,'Invalid tool result identity')
        if message['role']=='tool' and 'tool_call_id' not in message:raise AdmissionError(400,'Tool result identity is required')
        if 'tool_calls' in message and (message['role']!='assistant' or not isinstance(message['tool_calls'],list) or not 1<=len(message['tool_calls'])<=32 or not all(call_valid(c) for c in message['tool_calls'])):raise AdmissionError(400,'Invalid assistant tool calls')
        for key in ('refusal','reasoning_content'):
            if key in message and message[key] is not None and (message['role']!='assistant' or not isinstance(message[key],str)):raise AdmissionError(400,'Invalid assistant text field')
        content=message.get('content')
        if isinstance(content,list):
            if any(not isinstance(p,dict) or p.get('type')!='text' or not isinstance(p.get('text'),str) for p in content):raise AdmissionError(400,'Initial capability accepts text only')
        elif content is not None and not isinstance(content,str):raise AdmissionError(400,'Unsupported message content')
        if content is None and not (message.get('role')=='assistant' and (message.get('tool_calls') or isinstance(message.get('refusal'),str))):
            raise AdmissionError(400,'Message content is required')
    tool_names=set()
    if 'tools' in body:
        if not isinstance(body['tools'],list) or len(body['tools'])>64:raise AdmissionError(400,'Invalid tool definitions')
        for tool in body['tools']:
            shape(tool,('type','function'),'Invalid tool definition')
            if tool.get('type')!='function':raise AdmissionError(400,'Only function tools are supported')
            function=tool.get('function');shape(function,('name','description','parameters','strict'),'Invalid function definition')
            if not name_string(function.get('name')):raise AdmissionError(400,'Invalid function name')
            if function['name'] in tool_names:raise AdmissionError(400,'Duplicate function name')
            tool_names.add(function['name'])
            if 'description' in function and not isinstance(function['description'],str):raise AdmissionError(400,'Invalid function description')
            if 'parameters' in function and not isinstance(function['parameters'],dict):raise AdmissionError(400,'Function parameters must be a schema object')
            if 'strict' in function and type(function['strict']) is not bool:raise AdmissionError(400,'strict must be boolean')
    if 'tool_choice' in body:
        choice=body['tool_choice']
        if isinstance(choice,str):
            if choice not in ('none','auto','required') or (choice=='required' and not tool_names):raise AdmissionError(400,'Invalid tool choice')
        else:
            shape(choice,('type','function'),'Invalid tool choice')
            function=choice.get('function');shape(function,('name',),'Invalid tool choice')
            if choice.get('type')!='function' or not name_string(function.get('name')) or function.get('name') not in tool_names:raise AdmissionError(400,'Tool choice must select a declared function')
    for key,low,high in (('temperature',0,2),('top_p',0,1),('presence_penalty',-2,2),('frequency_penalty',-2,2)):
        if key in body and (type(body[key]) not in (int,float) or not low<=body[key]<=high):raise AdmissionError(400,'Invalid sampling option')
    if 'seed' in body and (type(body['seed']) is not int or not -(2**63)<=body['seed']<2**63):raise AdmissionError(400,'Invalid seed')
    if 'parallel_tool_calls' in body and type(body['parallel_tool_calls']) is not bool:raise AdmissionError(400,'parallel_tool_calls must be boolean')
    if 'stream_options' in body:
        shape(body['stream_options'],('include_usage',),'Unsupported stream options')
        if any(type(v) is not bool for v in body['stream_options'].values()):raise AdmissionError(400,'Invalid stream option value')
    if 'stop' in body and not (isinstance(body['stop'],str) or isinstance(body['stop'],list) and 1<=len(body['stop'])<=4 and all(isinstance(v,str) for v in body['stop'])):raise AdmissionError(400,'Invalid stop sequence')
    if 'user' in body and (not isinstance(body['user'],str) or len(body['user'])>200):raise AdmissionError(400,'Invalid client attribution')
    if 'response_format' in body:
        form=body['response_format'];shape(form,('type','json_schema'),'Unsupported response format')
        if form.get('type') not in ('text','json_object','json_schema'):raise AdmissionError(400,'Unsupported response format')
        if form['type']=='json_schema':
            schema=form.get('json_schema');shape(schema,('name','description','schema','strict'),'Invalid response schema')
            if not name_string(schema.get('name')) or not isinstance(schema.get('schema'),dict):raise AdmissionError(400,'Invalid response schema')
            if 'description' in schema and not isinstance(schema['description'],str):raise AdmissionError(400,'Invalid response schema description')
            if 'strict' in schema and type(schema['strict']) is not bool:raise AdmissionError(400,'Invalid response strictness')
    if body.get('n',1)!=1 or type(body.get('n',1)) is not int:raise AdmissionError(400,'Exactly one completion is allowed')
    if 'max_tokens' in body and 'max_completion_tokens' in body:raise AdmissionError(400,'Specify one output token limit')
    key='max_completion_tokens' if 'max_completion_tokens' in body else 'max_tokens'
    maximum=body.get(key,config.get('max_tokens',4096))
    if type(maximum) is not int or not 1<=maximum<=config.get('max_tokens',4096):raise AdmissionError(400,'Output token limit exceeds this lease')
    if 'stream' in body and type(body['stream']) is not bool:raise AdmissionError(400,'stream must be boolean')
    result=dict(body);result[key]=maximum
    return result,maximum


class GatewayServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,config,token,transport,clock=time.time):
        if address[0]!='127.0.0.1':raise ValueError('Gateway must bind loopback behind the authenticated private transport')
        self.config=dict(config);self.token=token;self.transport=transport;self.clock=clock
        self.budget=Budget(config,clock)
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.settimeout(5)
    def log_message(self,*args):pass  # Never log prompts, bodies, tokens or arbitrary URLs.
    def authorized(self):
        value=self.headers.get('Authorization','')
        return hmac.compare_digest(value,'Bearer '+self.server.token)
    def reply(self,status,value):
        data=json.dumps(value).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def error(self,status,message):self.reply(status,{'error':{'message':message,'type':'bounded_gateway','code':status}})
    def do_GET(self):
        if not self.authorized():self.error(401,'Client credential required');return
        if self.path=='/health':self.reply(200,self.server.budget.status())
        elif self.path=='/v1/models':self.reply(200,{'object':'list','data':[{'id':self.server.config['model'],'object':'model','created':0,'owned_by':'runpod'}]})
        else:self.error(404,'Unsupported route')
    def do_POST(self):
        if not self.authorized():self.close_connection=True;self.error(401,'Client credential required');return
        if self.path!='/v1/chat/completions':self.close_connection=True;self.error(404,'Unsupported route');return
        request_id=None;admitted=False;headers_sent=False;success=False;usage=None
        try:
            if self.headers.get('Transfer-Encoding'):raise AdmissionError(400,'Chunked request bodies are unsupported')
            try:length=int(self.headers.get('Content-Length','-1'))
            except ValueError:raise AdmissionError(400,'Invalid Content-Length') from None
            if length<0:raise AdmissionError(411,'Content-Length is required')
            if length>self.server.config.get('max_body_bytes',16384):raise AdmissionError(413,'Request body too large')
            raw=self.rfile.read(length)
            if len(raw)!=length:raise AdmissionError(400,'Incomplete request body')
            try:decoded=json.loads(raw)
            except (ValueError,UnicodeDecodeError,RecursionError):raise AdmissionError(400,'Invalid JSON request body') from None
            body,maximum=validate_body(decoded,self.server.config)
            request_id=self.headers.get('Idempotency-Key') or self.headers.get('X-Request-ID') or str(uuid.uuid4())
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',request_id):raise AdmissionError(400,'Invalid request identity')
            self.server.budget.reserve(request_id,len(raw),maximum);admitted=True
            if self.server.clock()>=self.server.config['deadline']:raise AdmissionError(410,'Lease expired before dispatch')
            started=time.monotonic()
            with self.server.transport(body) as upstream:
                if upstream.status!=200:raise AdmissionError(502,'Unexpected upstream status')
                response_type=upstream.headers.get('Content-Type','application/json')
                streaming=response_type.startswith('text/event-stream')
                if not streaming and not response_type.startswith('application/json'):
                    raise AdmissionError(502,'Unsupported upstream response type')
                total=0;buffer=b'';json_parts=[];saw_choice=False;done=False
                if streaming:
                    self.send_response(200);self.send_header('Content-Type','text/event-stream')
                    self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers()
                    headers_sent=True;self.close_connection=True
                def check_time():
                    remaining=min(30-(time.monotonic()-started),self.server.config['deadline']-self.server.clock())
                    if remaining<=0:raise TimeoutError('Request timebox/lease ended')
                    return min(20,remaining)
                while True:
                    remaining=check_time()
                    if hasattr(upstream,'set_read_timeout'):upstream.set_read_timeout(remaining)
                    chunk=upstream.read1(4096)
                    check_time()  # A blocking read must never release content after expiry.
                    if not chunk:break
                    total+=len(chunk)
                    if total>1_048_576:raise ValueError('Upstream response exceeds limit')
                    if not streaming:json_parts.append(chunk);continue
                    buffer+=chunk
                    while True:
                        boundary=re.search(br'\r?\n\r?\n',buffer)
                        if boundary is None:break
                        frame=buffer[:boundary.end()];buffer=buffer[boundary.end():]
                        data_lines=[line.split(b':',1)[1].lstrip(b' ') for line in frame.splitlines() if line.startswith(b'data:')]
                        data=b'\n'.join(data_lines)
                        if data==b'[DONE]':done=True
                        elif data:
                            event=json.loads(data)
                            if not isinstance(event,dict) or event.get('error') is not None:raise ValueError('Provider stream error')
                            if 'choices' in event:
                                if not choices_valid(event['choices'],True):raise ValueError('Malformed stream choices')
                                saw_choice=saw_choice or bool(event['choices'])
                            elif 'usage' not in event:raise ValueError('Unsupported provider stream event')
                            usage=event.get('usage') or usage
                        check_time()
                        self.wfile.write(frame);self.wfile.flush()
                        if done:break
                    if len(buffer)>131072:raise ValueError('SSE frame exceeds limit')
                    if done:break
                if streaming:
                    success=done and saw_choice
                else:
                    data=b''.join(json_parts);result=json.loads(data)
                    if not isinstance(result,dict) or result.get('error') is not None or not choices_valid(result.get('choices')):
                        raise AdmissionError(502,'Incomplete provider completion')
                    usage=result.get('usage')
                    self.send_response(200);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers()
                    headers_sent=True;self.wfile.write(data);self.wfile.flush();success=True
        except AdmissionError as exc:
            success=False
            if not headers_sent:self.close_connection=True;self.error(exc.status,str(exc))
        except urllib.error.HTTPError as exc:
            success=False
            if not headers_sent:self.close_connection=True;self.error(502,f'Provider rejected request (HTTP {exc.code}); no automatic retry')
        except (TimeoutError,OSError):
            success=False
            if not headers_sent:self.close_connection=True;self.error(504,'Upstream request failed or timed out; no automatic retry')
        except (ValueError,TypeError,urllib.error.URLError):
            success=False
            if not headers_sent:self.close_connection=True;self.error(502,'Invalid upstream response; no automatic retry')
        finally:
            if admitted:self.server.budget.finish(request_id,success,usage if isinstance(usage,dict) else None)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args();config=json.loads(args.config.read_text());validate_config(config)
    token=secret_file(config['client_token_file'])
    if len(token)<32:raise ValueError('Client token is too short')
    server=GatewayServer(('127.0.0.1',int(config.get('port',19378))),config,token,native_transport(config))
    def expiry():
        while time.time()<config['deadline']:time.sleep(min(1,max(0,config['deadline']-time.time())))
        server.shutdown()
    threading.Thread(target=expiry,daemon=True).start()
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()


if __name__=='__main__':main()
