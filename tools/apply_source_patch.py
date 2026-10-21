"""Independent Python reference application of the source-relative patch."""
from __future__ import annotations
import argparse,base64,hashlib,json,os,shutil,struct,tempfile,zlib
from pathlib import Path
from mdec_delta import apply_edit

EDC=[];F=[];B=[0]*256
for i in range(256):
    v=i
    for _ in range(8):v=(v>>1)^(0xD8018001 if v&1 else 0)
    EDC.append(v);F.append(((i<<1)^(0x11d if i&128 else 0))&255)
for i in range(256):B[i^F[i]]=i

def ecc(sector,major_count,minor_count,major_mult,minor_inc):
    size=major_count*minor_count;out=bytearray(major_count*2)
    for major in range(major_count):
        index=((major>>1)*major_mult+(major&1))%size;a=b=0
        for _ in range(minor_count):
            value=sector[12+index];index=(index+minor_inc)%size;a^=value;b^=value;a=F[a]
        a=B[F[a]^b];out[major]=a;out[major+major_count]=a^b
    return out

def rebuild(sector):
    sector=bytearray(sector);v=0
    if len(sector)!=2352 or sector[15]!=2 or sector[18]&32:raise ValueError('Unexpected sector')
    for b in sector[16:2072]:v=(v>>8)^EDC[(v^b)&255]
    sector[2072:2076]=struct.pack('<I',v)
    sector[2076:2248]=ecc(sector,86,24,2,86);sector[2248:2352]=ecc(sector,52,43,86,88)
    return sector

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def load(path):
    raw=path.read_bytes()
    if raw[:9]!=b'OTOPATCH2':raise ValueError('Unexpected patch version')
    data=zlib.decompress(raw[13:],-15)
    if len(data)!=struct.unpack_from('<I',raw,9)[0]:raise ValueError('Truncated recipe')
    return json.loads(data)

def apply(source,patch,dest,vlc_path):
    if dest.exists() or source.resolve()==dest.resolve():raise FileExistsError(dest)
    d=load(patch)
    if source.stat().st_size!=d['size'] or sha(source)!=d['source_sha256']:raise ValueError('Wrong source BIN')
    vlc={}
    for line in vlc_path.read_text(encoding='ascii').splitlines():
        if line and not line.startswith('#'):
            code,bits=line.split(':');vlc[int(code)]=bits
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.otogirisou-reference-',dir=dest.parent);os.close(fd);tmp=Path(temp)
    try:
        shutil.copyfile(source,tmp)
        with source.open('rb') as original,tmp.open('r+b') as output:
            for m in d['mdec']:
                data=[]
                for pos,n in m['extents']:original.seek(pos);data.append(original.read(n))
                changes=[None if b is None else list(zip(b[::2],b[1::2])) for b in m['blocks']]
                edit={'edits':changes,'header_edits':list(zip(m['header'][::2],m['header'][1::2])),
                      'tail':m['tail'],'stream_length':m['stream_length']}
                target=apply_edit(b''.join(data),edit,vlc);cursor=0
                for pos,capacity in m['extents']:
                    n=min(capacity,len(target)-cursor)
                    if n>0:output.seek(pos);output.write(target[cursor:cursor+n]);cursor+=n
            for dest_pos,source_pos,n in d['copies']:
                original.seek(source_pos);data=original.read(n);output.seek(dest_pos);output.write(data)
            for w in d['writes']:output.seek(w['offset']);output.write(base64.b64decode(w['data']))
            for pos,n,value in d['fills']:output.seek(pos);output.write(bytes([value])*n)
            for lba in d['ecc_sectors']:
                output.seek(lba*2352);sector=output.read(2352);output.seek(lba*2352);output.write(rebuild(sector))
        result=sha(tmp)
        if result!=d['target_sha256']:raise ValueError('Target SHA-256 mismatch: '+result)
        # Windows rename is atomic and refuses an existing destination. A hard
        # link is not available in every managed Windows filesystem sandbox.
        if os.name=='nt':os.rename(tmp,dest)
        else:os.link(tmp,dest);tmp.unlink()
        return {'result':'PASS','sha256':result,'size':dest.stat().st_size,'application':'independent-python'}
    finally:
        if tmp.exists():tmp.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['source','patch','output','vlc']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();print(json.dumps(apply(a.source,a.patch,a.output,a.vlc)),flush=True)
