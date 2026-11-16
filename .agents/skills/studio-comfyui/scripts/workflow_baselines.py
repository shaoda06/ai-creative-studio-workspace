#!/usr/bin/env python3
"""Offline checks of bundled API structure and execution parameters. Never reads canvas files or connects."""
import argparse, ast, copy, json, math, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio-comfyui/scripts"))
from workflow_graph import Canvas, is_link, link_tuple
from workflow_paths import VIDEO_RELAYVSR, VIDEO_RIFE, VIDEO_RTX, workflow_directories, workflow_root, SKILL_ROOT
UI_FIELDS={'control_after_generate','upload','choose video to upload','videopreview','image_upload','audioUI','preview'}
UI_NODES={'Note','MarkdownNote','SetNode','GetNode','Reroute'}

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

def validate_postprocess(api):
 encode=api['16']['inputs']
 image,fps=['7',0],['7',2]
 details={'format':encode['format'],'crf':encode['crf']}
 if '12' in api:
  interpolation=api['12']
  assert interpolation['class_type']=='NoraRIFEInterpolationCutTest', 'Postprocess interpolation node mismatch'
  values=interpolation['inputs']
  assert {'scale','scene_cut_threshold'}<=set(values), 'Missing required RIFE inputs'
  assert values['images']==image and values['source_fps']==fps, 'Postprocess source images/FPS mismatch'
  details['target_fps']=values['target_fps']
  image,fps=['12',0],['12',1]
 if '1' in api:
  resize=api['1']['inputs']
  assert api['1']['class_type']=='RTXVideoSuperResolution', 'Postprocess image processing node mismatch'
  assert resize['images']==image, 'Postprocess RTX inputs must follow any interpolation'
  details.update(width=resize['resize_type.width'],height=resize['resize_type.height'])
  image=['1',0]
 assert image!=['7',0] and encode['images']==image, 'Postprocess encoder must use processed images'
 assert encode['frame_rate']==fps, 'Postprocess output FPS must follow frame source'
 assert encode['audio']==['7',1] and encode['trim_to_audio'] is False, 'Postprocess original audio/timing mismatch'
 notes=[]
 if 'width' in details and min(details['width'],details['height'])<1080:notes.append('低于推荐1080P；按本次选定交付依据核对')
 if 'target_fps' in details and details['target_fps']<30:notes.append('低于推荐30fps；按本次选定交付依据核对')
 return dict(details,recommendation_notes=notes)

def validate_relayvsr(api):
 assert api['4']['inputs']['unet_name'].endswith('relayvsr_x2_lightx2v_int8_convrot.safetensors')
 assert api['7']['inputs']['vae_name'].endswith('relayvsr_flash_vae_x2_fp32.safetensors')
 assert api['6']['inputs']['steps']==api['6']['inputs']['cfg']==1
 assert api['104']['inputs']=={'detail':0.5,'vae':['7',0],'samples':['6',0],'images':['2',0]}
 assert api['105']['inputs']['images']==['104',0]
 assert api['105']['inputs']['fps']==['2',2] and api['105']['inputs']['audio']==['2',1]
 assert api['106']['inputs']['video']==['105',0]

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

def output_for(name):
 if name==VIDEO_RELAYVSR:return 106
 if name in ('Viggle-Remake-单人换人-双参考图', 'Viggle-Remake-换背景-目标参考帧'):return 65
 return 404 if name=='MiniMax-H3-Songssx导演台-Selflift-标准版' else [403,504,506] if name=='Minimax-H3-导演台-视频生成-标准版' else 3 if name=='RTX-图片2倍超分' else 508 if name=='Qwen2.1-文生图-普通版' else 487 if name=='Qwen2.1-图生图-普通版' else 461 if name.startswith('Qwen') else 16

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
  if stem in (VIDEO_RIFE, VIDEO_RTX):
   result['postprocess_delivery']=validate_postprocess(actual)
   if stem==VIDEO_RIFE:
    package=Path(__file__).resolve().parents[1]/'dependencies/ComfyUI节点资源/ComfyUI-Nora-RIFE-CutTest.zip'
    validate_rife_package(package)
    result['node_package']=package.name
  if stem==VIDEO_RELAYVSR:validate_relayvsr(actual)
  results.append(result)
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__, epilog='Python 3.9+, standard library; do not use -O. Prints one JSON line per scanned API, then PASS; exit 0 on success, nonzero on error. Check expected workflow coverage: an empty directory can also pass.')
 p.add_argument('--directory',type=Path,default=workflow_root(),help='Scan bundled-name *.api.json files in this directory and its immediate category directories registered in workflow_paths.py, excluding other or deeper directories. Default: the tool-owned workflow locations registered in workflow_paths; relative paths use the current working directory. Point directly at a category directory to check only its APIs.')
 args=p.parse_args()
 for r in verify(args.directory):print(json.dumps(r,ensure_ascii=False))
 print('PASS: offline API checks only; remote compatibility and execution not tested.')
