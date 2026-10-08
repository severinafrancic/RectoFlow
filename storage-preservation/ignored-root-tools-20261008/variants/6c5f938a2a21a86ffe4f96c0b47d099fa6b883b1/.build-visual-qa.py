from pathlib import Path
import json, subprocess, sys
from PIL import Image, ImageDraw
import edge_capture as core

root=Path(__file__).parent
folder=root/'.build-qa'
folder.mkdir(exist_ok=True)
cfg=json.loads((root/'config.json').read_text())
cfg.update(regions=[[20,30,210,297],[260,30,210,297]],navigation_mode='none')
screen=Image.new('RGB',(500,350),'white')
draw=ImageDraw.Draw(screen)
for number,rect,color in zip((1,2),cfg['regions'],('#e8eefc','#e5f5eb')):
    x,y,w,h=rect
    draw.rectangle((x,y,x+w-1,y+h-1),fill=color,outline='black',width=2)
    draw.text((x+20,y+30),f'RECTOFLOW - REGION {number}',fill='black')
    draw.text((x+20,y+65),'Ordered capture / PDF export',fill='black')
record=core.save_pair(folder,1,screen,cfg)
core.write_json(folder/'manifest.json',{'schema':2,'status':'COMPLETE','config':cfg,'pairs':[record]})
exe=root/'.build-dist'/'RectoFlow'/'RectoFlow.exe'
for paper,direction,layout in [('A4','portrait','separate'),('A5','landscape','spread')]:
    result=subprocess.run([str(exe),'--rebuild',str(folder),'--paper',paper,'--orientation',direction,'--layout',layout],capture_output=True,text=True,check=True)
    output=Path(result.stdout.strip().splitlines()[-1])
    poppler=Path(r'C:\Users\sever\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
    subprocess.run([str(poppler),'-png','-scale-to','900','-f','1','-singlefile',str(output),str(folder/(paper+'-'+direction))],check=True)
    print(output.name)
