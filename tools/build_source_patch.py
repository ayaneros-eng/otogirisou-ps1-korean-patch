"""Build a source-dependent R152 patch without sector/image/video literals."""
from __future__ import annotations
import argparse, base64, collections, hashlib, json, mmap, struct, zlib
from pathlib import Path
from mdec_delta import make_edit

SOURCE_SHA = '81a130ca6daacf7bf60f2808bb20262e274477ecbfe4ffdec739f00017db58f8'
TARGET_SHA = 'ff7fd8379be4f342d18008fedf19ca13a2ca3dbcd1cd510284e387341f0cfb5c'
SIZE = 712192656
FILES = {'CDIMG.BIN': (277209,11282432), 'SLPS_016.45': (282718,440320),
         'OTOMV2/MOV100.STR': (142007,33210368),
         'OTOMV/MOV026.STR': (237145,31457280), 'OTOMV/MOV027.STR': (252505,31457280)}

def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def extents(lba, offset, length):
    result=[]
    while length:
        sector, inside=divmod(offset,2048)
        n=min(2048-inside,length)
        result.append([2352*(lba+sector)+24+inside,n])
        offset+=n;length-=n
    return result

def gather(mm, spans):
    return b''.join(mm[p:p+n] for p,n in spans)

def clipped(spans, length):
    result=[]
    for pos,size in spans:
        n=min(size,length)
        if n:result.append([pos,n])
        length-=n
    if length:raise ValueError('Extent capacity exceeded')
    return result

def source_copy_split(pos, data, source_code, index, stats):
    result=[];start=cursor=0
    while cursor+16<=len(data):
        candidates=index.get(data[cursor:cursor+16],[])
        best_n=best_at=0
        for at in candidates:
            n=16
            while cursor+n<len(data) and at+n<len(source_code) and data[cursor+n]==source_code[at+n]:n+=1
            if n>best_n:best_n,best_at=n,at
        if best_n>=16:
            if cursor>start:result.append([0,pos+start,base64.b64encode(data[start:cursor]).decode('ascii')])
            # The source executable uses a 2048-byte logical view, so split
            # a copied range into raw-disc extents before serializing.
            dest=pos+cursor
            for src,n in extents(FILES['SLPS_016.45'][0],best_at,best_n):
                result.append([1,dest,src,n]);dest+=n
            stats['relocated_original_code_source_copy_bytes']+=best_n
            cursor+=best_n;start=cursor
        else:cursor+=1
    if start<len(data):result.append([0,pos+start,base64.b64encode(data[start:]).decode('ascii')])
    return result

def build(source,target,output,vlc_path,graphics_path,report_path):
    for p,expected in [(source,SOURCE_SHA),(target,TARGET_SHA)]:
        if p.stat().st_size!=SIZE or sha_file(p)!=expected:raise ValueError('Input hash mismatch: '+str(p))
    table=vlc_path.read_text(encoding='utf8')
    if table.lstrip().startswith('{'):vlc={int(k):v for k,v in json.loads(table).items()}
    else:vlc={int(line.split(':')[0]):line.split(':')[1] for line in table.splitlines() if line and not line.startswith('#')}
    graphics=json.loads(graphics_path.read_text(encoding='utf8'))
    stats=collections.Counter();frames={};records=[];skip=[]
    with source.open('rb') as sf,target.open('rb') as tf:
        old=mmap.mmap(sf.fileno(),0,access=mmap.ACCESS_READ);new=mmap.mmap(tf.fileno(),0,access=mmap.ACCESS_READ)
        changed=[i for i in range(SIZE//2352) if old[i*2352:(i+1)*2352]!=new[i*2352:(i+1)*2352]]
        changed_set=set(changed)
        def record(label,spans,frame=False):
            a=gather(old,spans);b=gather(new,spans)
            edit,counts=make_edit(a,b,vlc)
            blocks=[None if e is None else [n for pair in e for n in pair] for e in edit['edits']]
            record={'label':label,'extents':spans,'blocks':blocks,
                    'header':[n for pair in edit['header_edits'] for n in pair],
                    'tail':edit['tail'],'stream_length':edit['stream_length']}
            records.append(record);skip.extend(clipped(spans,edit['stream_length']))
            stats.update(counts);stats['mdec_streams']+=1;stats['mdec_reconstructed_bytes']+=edit['stream_length']
            if frame:stats['video_frames']+=1
            else:stats['bs_images']+=1
        for g in graphics:
            if g.get('format')=='raw8bpp':continue
            record('image/'+g['name'],extents(FILES['CDIMG.BIN'][0],g['offset'],g['allocation']))
        for name in ['OTOMV2/MOV100.STR','OTOMV/MOV026.STR','OTOMV/MOV027.STR']:
            lba,size=FILES[name];chunks=collections.defaultdict(dict)
            for i in range((size+2047)//2048):
                off=(lba+i)*2352+24;p=new[off:off+2048]
                if p[:4]!=b'\x60\x01\x01\x80':continue
                c,n,k,length,w,h=struct.unpack_from('<HHIIHH',p,4)
                if (w,h)!=(320,240):raise ValueError('Unexpected dimensions')
                chunks[k][c]=[off+32,2016]
            count=0
            for frame,pieces in sorted(chunks.items()):
                spans=[pieces[c] for c in range(len(pieces))]
                if any(p//2352 in changed_set for p,n in spans):
                    record(name+'/'+str(frame),spans,True);count+=1
            frames[name]=count
        # A covered prefix is produced from source coefficients, never copied
        # into generic byte literals as an already-completed BS frame.
        excluded=collections.defaultdict(list)
        for pos,n in skip:
            assert pos//2352==(pos+n-1)//2352
            excluded[pos//2352].append((pos%2352,pos%2352+n))
        code=gather(old,extents(FILES['SLPS_016.45'][0],0,FILES['SLPS_016.45'][1]))
        code_index=collections.defaultdict(list)
        for i in range(len(code)-15):
            key=code[i:i+16]
            if any(key) and len(code_index[key])<8:code_index[key].append(i)
        writes=[];copies=[];fills=[]
        for lba in changed:
            start=lba*2352;a=old[start:start+2352];b=new[start:start+2352]
            if a[:24]!=b[:24]:raise ValueError('Unexpected sector header change')
            if a[15]!=2 or a[18]&0x20:raise ValueError('Expected Mode2/Form1')
            allowed=bytearray(b'\1'*2048)
            for x,y in excluded[lba]:allowed[x-24:y-24]=bytes(y-x)
            j=0
            while j<2048:
                if not allowed[j] or a[j+24]==b[j+24]:j+=1;continue
                k=j+1
                while k<2048 and allowed[k] and a[k+24]!=b[k+24]:k+=1
                pos=start+24+j;data=b[24+j:24+k]
                if len(set(data))==1 and len(data)>=4:
                    fills.append([pos,len(data),data[0]])
                else:
                    for op in source_copy_split(pos,data,code,code_index,stats):
                        if op[0]==0:writes.append({'offset':op[1],'data':op[2]})
                        else:copies.append(op[1:])
                j=k
        # Remove long original CDIMG spans retained at a different address,
        # including coincidentally repeated constants and relocated routines.
        # Index only prefixes actually present in the candidate literals; this
        # avoids indexing the entire disc or retaining game data in the patch.
        wanted={data[i:i+32] for w in writes for data in [base64.b64decode(w['data'])] for i in range(len(data)-31)}
        cdimg=gather(old,extents(FILES['CDIMG.BIN'][0],0,FILES['CDIMG.BIN'][1]))
        found={}
        for i in range(len(cdimg)-31):
            key=cdimg[i:i+32]
            if key in wanted and key not in found:found[key]=i
        refined=[]
        for w in writes:
            data=base64.b64decode(w['data']);pos=w['offset'];cursor=start=0
            while cursor<len(data):
                end=cursor+1
                while end<len(data) and data[end]==data[cursor]:end+=1
                fill=end-cursor>=4
                at=found.get(data[cursor:cursor+32]) if cursor+32<=len(data) else None
                if not fill and at is None:cursor+=1;continue
                if cursor>start:refined.append({'offset':pos+start,'data':base64.b64encode(data[start:cursor]).decode('ascii')})
                if fill:fills.append([pos+cursor,end-cursor,data[cursor]]);cursor=end
                else:
                    n=32
                    while cursor+n<len(data) and at+n<len(cdimg) and data[cursor+n]==cdimg[at+n]:n+=1
                    dest=pos+cursor
                    for src,count in extents(FILES['CDIMG.BIN'][0],at,n):copies.append([dest,src,count]);dest+=count
                    stats['additional_original_CDIMG_source_copy_bytes']+=n;cursor+=n
                start=cursor
            if start<len(data):refined.append({'offset':pos+start,'data':base64.b64encode(data[start:]).decode('ascii')})
        writes=refined
        old.close();new.close()
    payload={'format':2,'source_sha256':SOURCE_SHA,'target_sha256':TARGET_SHA,'size':SIZE,
             'mdec':records,'writes':writes,'copies':copies,'fills':fills,'ecc_sectors':changed}
    raw=json.dumps(payload,separators=(',',':'),ensure_ascii=True).encode('ascii')
    compressor=zlib.compressobj(9,zlib.DEFLATED,-15);packed=compressor.compress(raw)+compressor.flush()
    blob=b'OTOPATCH2'+struct.pack('<I',len(raw))+packed
    output.write_bytes(blob)
    stats.update({'changed_sectors':len(changed),'literal_write_records':len(writes),
                  'literal_bytes':sum(len(base64.b64decode(w['data'])) for w in writes),
                  'source_copy_records':len(copies),'fill_records':len(fills),
                  'fill_bytes':sum(x[1] for x in fills),'uncompressed_recipe_bytes':len(raw),'patch_bytes':len(blob)})
    report={'result':'BUILT_REQUIRES_APPLICATION_VERIFICATION','patch_sha256':hashlib.sha256(blob).hexdigest(),
            'source_sha256':SOURCE_SHA,'target_sha256':TARGET_SHA,'stats':dict(stats),'video_frames':frames,
            'full_sector_literals':0,'mdec_bitstream_literals':0}
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--target',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--vlc',type=Path,required=True)
    p.add_argument('--graphics',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();build(a.source,a.target,a.output,a.vlc,a.graphics,a.report)
