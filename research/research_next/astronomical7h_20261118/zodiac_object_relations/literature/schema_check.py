"""Standard-library validator for the exact keyword subset in schema_v1.json."""
def validate(value,schema,root=None,path='$'):
 root=schema if root is None else root
 if '$ref' in schema:
  sub=root
  for k in schema['$ref'].split('/')[1:]:sub=sub[k]
  return validate(value,sub,root,path)
 if 'const' in schema:assert value==schema['const'],(path,'const')
 if 'enum' in schema:assert value in schema['enum'],(path,'enum',value)
 types=schema.get('type');types=[types] if isinstance(types,str) else types
 test={'object':lambda x:isinstance(x,dict),'array':lambda x:isinstance(x,list),'string':lambda x:isinstance(x,str),'null':lambda x:x is None,'boolean':lambda x:isinstance(x,bool),'integer':lambda x:isinstance(x,int) and not isinstance(x,bool),'number':lambda x:isinstance(x,(int,float)) and not isinstance(x,bool)}
 if types:assert any(test[t](value) for t in types),(path,'type',type(value))
 if isinstance(value,dict):
  assert set(schema.get('required',[]))<=set(value),(path,'required')
  pp=schema.get('properties',{})
  if schema.get('additionalProperties') is False:assert set(value)<=set(pp),(path,'additionalProperties',set(value)-set(pp))
  for k,v in value.items():
   if k in pp:validate(v,pp[k],root,path+'.'+k)
 if isinstance(value,list):
  assert len(value)>=schema.get('minItems',0) and len(value)<=schema.get('maxItems',float('inf')),(path,'length')
  if 'items' in schema:
   for n,v in enumerate(value):validate(v,schema['items'],root,path+'['+str(n)+']')
