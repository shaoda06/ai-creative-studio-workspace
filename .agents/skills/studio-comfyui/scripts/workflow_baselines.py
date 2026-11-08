#!/usr/bin/env python3
"""Offline checks of bundled API structure and execution parameters. Never reads canvas files or connects."""
import argparse, ast, copy, json, math, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio-comfyui/scripts"))
from workflow_graph import Canvas, is_link, link_tuple
from workflow_paths import workflow_directories, workflow_root, SKILL_ROOT
UI_FIELDS={'control_after_generate','upload','choose video to upload','videopreview','image_upload','audioUI','preview'}
UI_NODES={'Note','MarkdownNote','SetNode','GetNode','Reroute'}
POSTPROCESS_NODES={'RTX-RIFE-自动切镜保护超分插帧':'NoraRIFEInterpolationCutTest',
                   'RIFE-自动切镜保护裁切':'NoraRIFEInterpolationCutTest'}

def validate_rife_package(path):
 with zipfile.ZipFile(path) as package:
  root='ComfyUI-Nora-RIFE-CutTest/'
  required={'__init__.py','nodes.py','cut_protection.py','preflight.py','smoke_test.py',
            'tests/test_cut_protection.py','README.md','LICENSE'}
  assert {root+name for name in required}<=set(package.namelist()), 'Incomplete RIFE node package'
  assert package.testzip() is None, 'Corrupt RIFE node package'
  tree=ast.parse(package.read(root+'nodes.py').decode('utf-8'))
  assert any(isinstance(n,ast.ClassDef) and n.name=='NoraRIFEInterpolationCutTest' for n in tree.body), 'RIFE package class mismatch'
  for name in package.namelist():
   if name.endswith('.py'):ast.parse(package.read(name).decode('utf-8'),filename=name)

def validate_postprocess(api,name):
 interpolation=api['12'];resize=api['1']['inputs'];encode=api['16']['inputs']
 expected='ImageCrop' if name=='RIFE-自动切镜保护裁切' else 'RTXVideoSuperResolution'
 assert api['1']['class_type']==expected, 'Postprocess image processing node mismatch'
 assert interpolation['class_type']==POSTPROCESS_NODES[name], 'Postprocess interpolation node mismatch'
 if interpolation['class_type']=='NoraRIFEInterpolationCutTest':
  assert {'scale','scene_cut_threshold'}<=set(interpolation['inputs']), 'Missing required RIFE inputs'
 frame_input='images' if interpolation['class_type']=='NoraRIFEInterpolationCutTest' else 'frames'
 assert interpolation['inputs'][frame_input]==['7',0], 'Postprocess source images mismatch'
 assert interpolation['inputs']['source_fps']==['7',2], 'Postprocess source FPS mismatch'
 if api['1']['class_type']=='ImageCrop':
  assert resize['image']==['12',0], 'Postprocess must interpolate before cropping'
  width,height=resize['width'],resize['height']
 else:
  assert resize['images']==['12',0], 'Postprocess must interpolate before upscaling'
  width,height=resize['resize_type.width'],resize['resize_type.height']
 assert encode['images']==['1',0], 'Postprocess encoder must use processed images'
 assert encode['frame_rate']==['12',1], 'Postprocess output FPS must follow interpolation'
 assert encode['audio']==['7',1] and encode['trim_to_audio'] is False, 'Postprocess original audio/timing mismatch'
 fps=interpolation['inputs']['target_fps']
 notes=[]
 if min(width,height)<1080:notes.append('低于推荐1080P；按本次选定交付依据核对，不因此拒绝本次交付配置')
 if fps<30:notes.append('低于推荐30fps；按本次选定交付依据核对，不因此拒绝本次交付配置')
 return {'width':width,'height':height,'target_fps':fps,'format':encode['format'],
         'crf':encode['crf'],'recommendation_notes':notes}

def semantic(api):return {k:{'class_type':v['class_type'],'inputs':v['inputs']} for k,v in api.items()}

def validate_rtx_inputs(api):
 """Check known required RTX inputs in new tasks, without querying the server."""
 for key,node in api.items():
  if node['class_type']!='RTXVideoSuperResolution':continue
  inputs=node['inputs']
  for field in ('strength','image_encoding'):
   if field not in inputs:raise ValueError(f'RTXVideoSuperResolution {key} missing required input: {field}')
  strength=inputs['strength']
  if type(strength) not in (int,float) or not math.isfinite(strength) or not 0<=strength<=1:
   raise ValueError(f'RTXVideoSuperResolution {key} strength must be a number from 0 to 1')
  if inputs['image_encoding'] not in ('8-bit RGB','10-bit RGB (RGB10A2)'):
   raise ValueError(f'RTXVideoSuperResolution {key} image_encoding is unsupported')

def output_for(name):return [403,504,506] if name=='Minimax-H3-导演台-视频生成-标准版' else 3 if name=='RTX-图片2倍超分' else 508 if name=='Qwen2.1-文生图-普通版' else 487 if name=='Qwen2.1-图生图-普通版' else 461 if name.startswith('Qwen') else 16

def director_editor_state(block, common=False):
 """Compare persisted Director content, excluding preview blobs and root-only fields."""
 if common:
  defaults={'commonEnabled':False,'commonCollapsed':False,'prompt':'','refs':[],'refAudios':[],'refVideos':[]}
  out={k:copy.deepcopy(block.get(k,v)) for k,v in defaults.items()}
  if 't2vCommon' in block:out['t2vCommon']=copy.deepcopy(block['t2vCommon'])
 else:
  out={k:copy.deepcopy(v) for k,v in block.items() if k not in {'previewB64','previewFrames','previewMime','imageB64'}}
  out.setdefault('loras',[])
 for field,file_key in [('refs','imageFile'),('refAudios','audioFile'),('refVideos','videoFile')]:
  defaults={file_key:'','fileName':'','type':'input','subfolder':''}
  if field!='refs':defaults['durationSec']=None
  if field=='refVideos':defaults['pairedAudioFile']=''
  out[field]=sorted(({'index':int(r.get('index',r.get('slot',0))),**{k:r.get(k,v) for k,v in defaults.items()}} for r in block.get(field,[])),key=lambda r:r['index'])
 if not common:
  for field in ['genImage','startImage','endImage','referenceVideo']:
   value=block.get(field)
   if value is None:out.pop(field,None);continue
   defaults={'imageFile':'','fileName':''} if field!='referenceVideo' else {'videoFile':'','fileName':'','type':'input','subfolder':''}
   if field in ('startImage','endImage'):defaults.update(width=0,height=0)
   out[field]={k:value.get(k,v) for k,v in defaults.items()}
 return out

def verify(directory):
 directory=Path(directory)
 folders=[directory, *(folder for folder,_ in workflow_directories(directory))]
 results=[]
 for a in sorted(p for folder in folders for p in folder.glob('*.api.json')):
  stem=a.name.removesuffix('.api.json');actual=json.loads(a.read_text(encoding="utf-8"))
  validate_rtx_inputs(actual)
  outputs=output_for(stem)
  for key in outputs if isinstance(outputs,list) else [outputs]:
   assert str(key) in actual, ('Missing API output',stem,key)
  for node in actual.values():
   for value in node['inputs'].values():
    if is_link(value):assert value[0] in actual, ('Missing API input',stem,value[0])
  refs=[(key,node['_meta']['nora_optional_reference']) for key,node in actual.items() if 'nora_optional_reference' in node.get('_meta',{})]
  assert len(refs)==(15 if '265' in actual and '多参考视频' in stem else 0)
  if stem=='RTX-图片2倍超分':
   assert actual['1']['inputs']['resize_type.scale']==2, 'Image upscale must remain 2x'
  for director in (n for n in actual.values() if n['class_type']=='MiniMaxH3Director'):
   inputs=director['inputs'];timeline=json.loads(inputs['timeline_data'])
   for field,key in [('width','width'),('height','height'),('ref_max_size','refMaxSize'),('frame_rate','frameRate'),('total_frames','totalFrames')]:
    assert inputs[field]==timeline[key],('Director timeline mismatch',field)
   assert timeline['output']['width']==inputs['width'] and timeline['output']['height']==inputs['height'], 'Director output size mismatch'
   assert timeline['global']['prompt']==inputs['global_prompt'], 'Director public prompt mismatch'
   assert sum(s['frameCount'] for s in timeline['segments'])==inputs['total_frames'], 'Director segment frame mismatch'
   workspace=timeline['batchWorkspaces']['r2v']
   assert director_editor_state(workspace['globalCommon'],True)==director_editor_state(timeline['global'],True), 'Director public workspace mismatch'
   assert [director_editor_state(s) for s in workspace['segments']]==[director_editor_state(s) for s in timeline['segments']], 'Director segment workspace mismatch'
   for field,default in [('selectedIndex',0),('editMode','segment'),('runSelectEnabled',False),('runSelection',[])]:
    assert workspace.get(field,default)==timeline.get(field,default),('Director selection workspace mismatch',field)
  # Exercise all supported reference-count combinations, removing unused loaders.
  count=0
  if refs:
   for ni in range(10):
    for na in range(4):
     for nv in range(4):
      if ni+na+nv>12 or (na and not(ni or nv)):continue
      task=copy.deepcopy(actual)
      for k,r in refs:
       group=r['input'].split('.')[0];limit={'ref_images':ni,'ref_audios':na,'ref_videos':nv}[group]
       if int(r['input'].rsplit('_',1)[1])<limit:task['265']['inputs'][r['input']]=[k,r['output_slot']]
       else:task.pop(k)
      for n in task.values():
       for v in n['inputs'].values():
        if is_link(v):assert v[0] in task
      count+=1
  result={'workflow':stem,'nodes':len(actual),'optional_references':len(refs),'reference_combinations':count}
  if stem in POSTPROCESS_NODES:
   result['postprocess_delivery']=validate_postprocess(actual,stem)
   if actual['12']['class_type']=='NoraRIFEInterpolationCutTest':
    package=Path(__file__).resolve().parents[1]/'dependencies/ComfyUI节点资源/ComfyUI-Nora-RIFE-CutTest.zip'
    validate_rife_package(package)
    result['node_package']=package.name
  results.append(result)
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__, epilog='Python 3.9+, standard library; do not use -O. Prints one JSON line per scanned API, then PASS; exit 0 on success, nonzero on error. Check expected workflow coverage: an empty directory can also pass.')
 p.add_argument('--directory',type=Path,default=workflow_root(),help='Scan bundled-name *.api.json files in this directory and its immediate category directories registered in workflow_paths.py, excluding other or deeper directories. Default: the tool-owned workflow locations registered in workflow_paths; relative paths use the current working directory. Point directly at a category directory to check only its APIs.')
 args=p.parse_args()
 for r in verify(args.directory):print(json.dumps(r,ensure_ascii=False))
 print('PASS: offline API checks only; remote compatibility and execution not tested.')
