"""Owned synthetic fixtures only; passwords exist solely in process memory."""
from io import BytesIO
import hashlib
from pathlib import Path
import secrets

def sha(raw):return hashlib.sha256(raw).hexdigest()

def create(folder):
    from PIL import Image
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, NumberObject, RectangleObject
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    buffer=BytesIO();pdf=canvas.Canvas(buffer,pagesize=(300,400),invariant=1)
    for width,height in [(300,400),(300,400),(400,200),(200,300)]:
        pdf.setPageSize((width,height))
        pdf.setFillColorRGB(1,1,1);pdf.rect(0,0,width,height,fill=1,stroke=0)
        for x,y,color in [(35,45,(1,0,0)),(width-55,45,(0,1,0)),(width-55,height-65,(0,0,1)),(35,height-65,(1,0,1))]:
            pdf.setFillColorRGB(*color);pdf.rect(x,y,15,15,fill=1,stroke=0)
        pdf.setFillColorRGB(0,0,0);pdf.drawString(70,height/2,'SYNTHETIC PDF - no user data')
        pdf.showPage()
    pdf.save()
    writer=PdfWriter()
    for page in PdfReader(BytesIO(buffer.getvalue())).pages:writer.add_page(page)
    writer.pages[0].cropbox=RectangleObject((20,30,280,370))
    writer.pages[0][NameObject('/Rotate')]=NumberObject(90)
    writer.pages[1].pop(NameObject('/CropBox'),None)
    writer._pages.get_object()[NameObject('/CropBox')]=RectangleObject((10,20,290,380))
    writer.pages[2].cropbox=RectangleObject((0,0,400,200))
    writer.pages[2][NameObject('/UserUnit')]=NumberObject(2)
    writer.pages[3].cropbox=RectangleObject((0,0,200,300))
    writer.pages[3][NameObject('/Rotate')]=NumberObject(180)
    output=BytesIO();writer.write(output);plain=output.getvalue()
    path=folder/'synthetic.pdf';path.write_bytes(plain)
    password=secrets.token_urlsafe(24)
    encrypted=PdfWriter();encrypted.clone_document_from_reader(PdfReader(BytesIO(plain)))
    encrypted.encrypt(password,owner_password=secrets.token_urlsafe(24),algorithm='RC4-128')
    output=BytesIO();encrypted.write(output)
    protected=folder/'encrypted.pdf';protected.write_bytes(output.getvalue())
    frames=[Image.new('RGB',size,color) for size,color in
            [((128,96),(220,20,20)),((96,128),(20,220,20)),((160,96),(20,20,220))]]
    tiff=folder/'multiframe.tiff';frames[0].save(tiff,save_all=True,append_images=frames[1:])
    bad=folder/'corrupt.pdf';bad.write_bytes(b'%PDF-1.7\nnot a PDF document\n')
    image=folder/'corrupt.png';image.write_bytes(b'\x89PNG\r\n\x1a\nnot a PNG')
    return {'pdf':str(path),'pdf_sha256':sha(plain),'encrypted':str(protected),
            'encrypted_sha256':sha(protected.read_bytes()),'password':password,
            'tiff':str(tiff),'tiff_sha256':sha(tiff.read_bytes()),
            'bad_pdf':str(bad),'bad_image':str(image)}

def container_proposals(source_id,frame_id,raster_hash,size,additional=()):
    """Contract probe, not a production ingestion adapter or detector."""
    width,height=size
    full={'origin':'CONTAINER_PAGE','kind':'FULL_FRAME','source_id':source_id,'frame_id':frame_id,
          'raster_sha256':raster_hash,'size':list(size),'quad':[[0,0],[width-1,0],[width-1,height-1],[0,height-1]],
          'acceptance':'REVIEW_REQUIRED'}
    return [full,*additional]
