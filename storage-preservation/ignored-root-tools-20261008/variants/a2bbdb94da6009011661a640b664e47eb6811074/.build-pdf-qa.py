from pathlib import Path
import json
import subprocess
from PIL import Image, ImageDraw
from pypdf import PdfReader
import edge_capture as core
from calibration.exports import create_plan, execute_plan

root=Path(__file__).resolve().parent
folder=root/'.build-pdf-qa';folder.mkdir(exist_ok=True)
cfg=json.loads((root/'config.json').read_bytes())
cfg.update(regions=[[10,20,300,180],[330,20,150,200]],navigation_mode='none')
image=Image.new('RGB',(510,240),'white');draw=ImageDraw.Draw(image)
for i,(rect,color) in enumerate(zip(cfg['regions'],['lightblue','lightyellow']),1):
    x,y,w,h=rect
    draw.rectangle((x,y,x+w-1,y+h-1),fill=color,outline='black',width=3)
    draw.text((x+15,y+15),f'REGION {i} - ALL FOUR BORDERS VISIBLE',fill='black')
    draw.text((x+15,y+45),'RectoFlow export QA',fill='black')
    for xx,yy in [(x,y),(x+w-8,y),(x,y+h-8),(x+w-8,y+h-8)]:draw.rectangle((xx,yy,xx+7,yy+7),fill='red')
record=core.save_pair(folder,1,image,cfg)
core.write_json(folder/'manifest.json',{'schema':3,'status':'COMPLETE','finished':'qa-complete','config':cfg,'pairs':[record],'profile':None})
poppler=r'C:\Users\sever\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe'
checks=[]
for paper in [*core.PAPER_MM,'Original']:
    for orientation in ('portrait','landscape'):
        for layout in ('separate','spread'):
            pdf=execute_plan(folder,create_plan(folder,options={'paper_format':paper,'paper_orientation':orientation,'pdf_layout':layout}))
            pages=PdfReader(pdf).pages
            assert len(pages)==(2 if layout=='separate' else 1)
            if paper!='Original':
                w,h=core.PAPER_MM[paper]
                if orientation=='landscape':w,h=h,w
                for page in pages:
                    assert abs(float(page.mediabox.width)*25.4/72-w)<.001
                    assert abs(float(page.mediabox.height)*25.4/72-h)<.001
            checks.append({'paper':paper,'orientation':orientation,'layout':layout,'pages':len(pages),'pdf_sha256':core.sha256(pdf)})
            if (paper,orientation,layout) in [('A4','portrait','separate'),('A5','landscape','spread'),('Original','portrait','separate')]:
                prefix=folder/f'{paper}-{orientation}-{layout}'
                subprocess.run([poppler,'-f','1','-singlefile','-scale-to','900','-png',str(pdf),str(prefix)],check=True,capture_output=True)
core.write_json(folder/'receipt.json',{'status':'PASS','exports':checks,'code_tree':core.code_identity()})
print(f'PDF_QA_PASS: {len(checks)} format/orientation/layout combinations')
