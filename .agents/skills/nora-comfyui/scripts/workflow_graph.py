"""Bundled ComfyUI graph conversion shared by image and existing video callers."""
import copy
UI_FIELDS={'audioUI', 'preview', 'control_after_generate', 'videopreview', 'upload', 'image_upload', 'choose video to upload'}
UI_NODES={'SetNode', 'Note', 'Reroute', 'GetNode', 'MarkdownNote'}

def is_link(v):return isinstance(v,list) and len(v)==2 and isinstance(v[0],str) and isinstance(v[1],int)

def link_tuple(l):
 return [l['id'],l['origin_id'],l['origin_slot'],l['target_id'],l['target_slot']] if isinstance(l,dict) else l[:5]

class Canvas:
 def __init__(self,g,prefix='',parent=None,instance=None,definitions=None):
  self.g=g;self.prefix=prefix;self.parent=parent;self.instance=instance
  self.nodes={n['id']:n for n in g['nodes']};self.links={x[0]:x for x in map(link_tuple,g.get('links',[]))}
  self.defs=definitions if definitions is not None else {d['id']:d for d in g.get('definitions',{}).get('subgraphs',[])}
  self.children={}
  assert len(self.nodes)==len(g['nodes']), 'Duplicate canvas node ID'
  assert len(self.links)==len(g.get('links',[])), 'Duplicate canvas link ID'
  for n in self.nodes.values():
   named=n.get('widgets_values_named',{});stored=n.get('widgets_values',[])
   if named:
    if isinstance(stored,list):assert stored==list(named.values()), ('Canvas widget mismatch',self.prefix,n['id'])
    else:
     for field,value in named.items():
      if field not in UI_FIELDS:assert stored.get(field)==value, ('Canvas widget mismatch',self.prefix,n['id'],field)
  for link_id,origin,slot,target,target_slot in self.links.values():
   if origin in self.nodes:
    assert link_id in (self.nodes[origin].get('outputs',[])[slot].get('links') or []), ('Broken output',link_id)
   else:assert parent and origin==g['inputNode']['id'], ('Missing source',origin)
   if target in self.nodes:
    assert self.nodes[target]['inputs'][target_slot].get('link')==link_id, ('Broken input',link_id)
   else:assert parent and target==g['outputNode']['id'], ('Missing target',target)
 def child(self,n):
  if n['id'] not in self.children:self.children[n['id']]=Canvas(self.defs[n['type']],self.prefix+str(n['id'])+':',self,n,self.defs)
  return self.children[n['id']]
 def follow(self,i,ignore=False,seen=()):
  l=self.links.get(i.get('link'));return self.resolve(l[1],l[2],ignore,seen) if l else None
 def resolve(self,id,slot=0,ignore=False,seen=()):
  key=(self.prefix,id,slot);assert key not in seen,('routing cycle',key);seen=seen+(key,)
  if self.parent and id==self.g['inputNode']['id']:
   i=self.instance['inputs'][slot]
   return self.parent.follow(i,ignore,seen) if i.get('link') is not None else self.instance.get('widgets_values_named',{}).get(i['name'])
  n=self.nodes[id]
  if n['type'] in self.defs:
   c=self.child(n);output=c.g['outputNode']['id'];ls=[l for l in c.links.values() if l[3]==output and l[4]==slot];assert len(ls)==1
   return c.resolve(ls[0][1],ls[0][2],ignore,seen)
  if n['type']=='GetNode':
   sets=[s for s in self.nodes.values() if s['type']=='SetNode' and s['widgets_values'][0]==n['widgets_values'][0]];assert len(sets)==1
   return self.resolve(sets[0]['id'],0,ignore,seen)
  if n['type'] in ('SetNode','Reroute'):return self.follow(n['inputs'][0],ignore,seen)
  if not ignore and n.get('mode')==2:return None
  if not ignore and n.get('mode')==4:
   ins=[i for i in n.get('inputs',[]) if i.get('link') is not None and i['type']==n.get('outputs',[])[slot]['type']];assert len(ins)<=1
   return self.follow(ins[0],ignore,seen) if ins else None
  return [self.prefix+str(id),slot]
 def object(self,id):
  n=self.nodes[id];v={k:copy.deepcopy(v) for k,v in n.get('widgets_values_named',{}).items() if k not in UI_FIELDS}
  for i in n.get('inputs',[]):
   if i.get('link') is not None:
    x=self.follow(i)
    if x is not None:v[i['name']]=x
    else:v.pop(i['name'],None)
  return {'class_type':n['type'],'inputs':v,'_meta':{'title':n.get('title',n['type'])}}
 def find(self,key):
  if ':' not in key:return self,int(key)
  id,rest=key.split(':',1);return self.child(self.nodes[int(id)]).find(rest)
 def active_nodes(self):
  for id,n in self.nodes.items():
   if n.get('mode',0) in (2,4):continue
   if n['type'] in self.defs:yield from self.child(n).active_nodes()
   elif n['type'] not in UI_NODES:yield self.prefix+str(id)
 def api(self,root,optional=True):
  out={};active=set()
  def walk(key):
   if key in out:return
   assert key not in active,('cycle',key);active.add(key);c,id=self.find(key);n=c.object(id)
   for v in n['inputs'].values():
    if is_link(v):walk(v[0])
   active.remove(key);out[key]=n
  for output in root if isinstance(root,(list,tuple)) else [root]:walk(str(output))
  if optional and 265 in self.nodes:
   for i in self.nodes[265]['inputs']:
    if i['name'].startswith(('ref_images.','ref_audios.','ref_videos.')) and i.get('link') is not None:
     src=self.follow(i,True);assert is_link(src);walk(src[0])
     out[src[0]]['_meta']['nora_optional_reference']={'target':'265','input':i['name'],'output_slot':src[1]}
  return out
