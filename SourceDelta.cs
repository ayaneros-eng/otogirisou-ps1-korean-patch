using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.IO.Compression;
using System.Reflection;
using System.Threading;

[DataContract] public sealed class MdecEdit {
    [DataMember] public string label;
    [DataMember] public int[][] extents;
    [DataMember] public int[][] blocks;
    [DataMember] public int[] header;
    [DataMember] public string tail;
    [DataMember] public int stream_length;
}
[DataContract] public sealed class ByteEdit {
    [DataMember] public int offset;
    [DataMember] public string data;
}
[DataContract] public sealed class DeltaDocument {
    [DataMember] public int format;
    [DataMember] public long size;
    [DataMember] public string source_sha256;
    [DataMember] public string target_sha256;
    [DataMember] public MdecEdit[] mdec;
    [DataMember] public ByteEdit[] writes;
    [DataMember] public int[][] copies;
    [DataMember] public int[][] fills;
    [DataMember] public int[] ecc_sectors;
}

public static class SourceDelta {
    static void Require(bool ok) { if(!ok)throw new InvalidDataException("원본 참조 패치의 구조가 올바르지 않습니다."); }
    static void Range(long at,long count,long size) { Require(at>=0&&count>0&&at<=size-count); }
    static void UserRange(long at,long count,long size) {
        Range(at,count,size);Require(at%2352>=24&&(at%2352)+count<=2072);
    }
    public static DeltaDocument Load(byte[] patch,PatchInfo meta) {
        Require(patch.Length>=14&&Encoding.ASCII.GetString(patch,0,9)=="OTOPATCH2");
        int length=BitConverter.ToInt32(patch,9);Require(length>0&&length<=32*1024*1024);
        byte[] raw;
        using(var input=new MemoryStream(patch,13,patch.Length-13))
        using(var compressed=new DeflateStream(input,CompressionMode.Decompress))
        using(var result=new MemoryStream()) {
            byte[] buffer=new byte[65536];int n;
            while((n=compressed.Read(buffer,0,buffer.Length))>0) {
                Require(result.Length+n<=length);result.Write(buffer,0,n);
            }
            Require(result.Length==length);raw=result.ToArray();
        }
        DeltaDocument d;
        using(var s=new MemoryStream(raw))d=(DeltaDocument)new DataContractJsonSerializer(typeof(DeltaDocument),new DataContractJsonSerializerSettings{MaxItemsInObjectGraph=16000000}).ReadObject(s);
        Require(d.format==2&&d.size==meta.source_size&&d.size==meta.target_size&&
                d.source_sha256==meta.source_sha256&&d.target_sha256==meta.target_sha256);
        Require(d.mdec!=null&&d.writes!=null&&d.copies!=null&&d.fills!=null&&d.ecc_sectors!=null);
        var ranges=new List<long[]>();
        Action<long,long> register=(at,count)=>{UserRange(at,count,d.size);ranges.Add(new[]{at,at+count});};
        foreach(var m in d.mdec) {
            Require(m.extents!=null&&m.extents.Length>0&&m.extents.Length<=128&&m.blocks!=null&&m.blocks.Length==1800);
            Require(m.header!=null&&m.header.Length%2==0&&m.header.Length<=16&&m.tail!=null&&m.tail.Length<=64);
            int capacity=0,remaining=m.stream_length;Require(remaining>=8);
            foreach(var e in m.extents) {
                Require(e!=null&&e.Length==2);UserRange(e[0],e[1],d.size);capacity=checked(capacity+e[1]);
                int count=Math.Min(remaining,e[1]);if(count>0){register(e[0],count);remaining-=count;}
            }
            Require(capacity<=512*1024&&m.stream_length<=capacity&&remaining==0);
            int previous=-1;
            for(int i=0;i<m.header.Length;i+=2){Require(m.header[i]>previous&&m.header[i]<8&&m.header[i+1]>=0&&m.header[i+1]<=255);previous=m.header[i];}
            foreach(char bit in m.tail)Require(bit=='0'||bit=='1');
            foreach(var changes in m.blocks)if(changes!=null) {
                Require(changes.Length%2==0&&changes.Length<=128);previous=-1;
                for(int i=0;i<changes.Length;i+=2) {
                    Require(changes[i]>previous&&changes[i]<64&&changes[i+1]>=-1023&&changes[i+1]<=1023);previous=changes[i];
                }
            }
        }
        foreach(var w in d.writes){Require(w!=null&&w.data!=null);register(w.offset,Convert.FromBase64String(w.data).Length);}
        foreach(var c in d.copies){Require(c!=null&&c.Length==3);register(c[0],c[2]);UserRange(c[1],c[2],d.size);}
        foreach(var f in d.fills){Require(f!=null&&f.Length==3&&f[2]>=0&&f[2]<=255);register(f[0],f[1]);}
        ranges.Sort((a,b)=>a[0].CompareTo(b[0]));
        for(int i=1;i<ranges.Count;i++)Require(ranges[i-1][1]<=ranges[i][0]);
        int last=-1;foreach(int lba in d.ecc_sectors){Require(lba>last&&(lba+1L)*2352<=d.size);last=lba;}
        return d;
    }
    public static byte[] ReadExact(Stream source,int count) {
        byte[] data=new byte[count];int offset=0;
        while(offset<count){int n=source.Read(data,offset,count-offset);if(n==0)throw new EndOfStreamException();offset+=n;}
        return data;
    }
    public static void Apply(Stream source,Stream output,DeltaDocument d,CancellationToken token,Action<int,string> progress) {
        int finished=0;
        foreach(var m in d.mdec) {
            token.ThrowIfCancellationRequested();
            byte[] original;
            using(var buffer=new MemoryStream()) {
                foreach(var e in m.extents){source.Position=e[0];byte[] part=ReadExact(source,e[1]);buffer.Write(part,0,part.Length);}
                original=buffer.ToArray();
            }
            byte[] target=BsSourceCodec.Apply(original,m);
            int at=0;
            foreach(var e in m.extents){int n=Math.Min(target.Length-at,e[1]);if(n>0){output.Position=e[0];output.Write(target,at,n);at+=n;}}
            if(at!=target.Length)throw new InvalidDataException("영상 변환 범위를 벗어났습니다.");
            finished++;progress(55+finished*24/d.mdec.Length,"원본에서 한글 화면·영상 생성 중");
        }
        foreach(var c in d.copies){token.ThrowIfCancellationRequested();source.Position=c[1];byte[] data=ReadExact(source,c[2]);output.Position=c[0];output.Write(data,0,data.Length);}
        foreach(var w in d.writes){token.ThrowIfCancellationRequested();byte[] data=Convert.FromBase64String(w.data);output.Position=w.offset;output.Write(data,0,data.Length);}
        foreach(var f in d.fills){token.ThrowIfCancellationRequested();byte[] data=new byte[f[1]];if(f[2]!=0)for(int i=0;i<data.Length;i++)data[i]=(byte)f[2];output.Position=f[0];output.Write(data,0,data.Length);}
        foreach(int lba in d.ecc_sectors) {
            token.ThrowIfCancellationRequested();output.Position=lba*2352L;byte[] sector=ReadExact(output,2352);
            CdChecksums.RebuildR152(sector);output.Position=lba*2352L;output.Write(sector,0,sector.Length);
        }
    }
}

public static class BsSourceCodec {
    sealed class Block { public int[] Coefficients;public int Start,Length; }
    static readonly Dictionary<string,int> Decode=new Dictionary<string,int>();
    static readonly Dictionary<int,string> Encode=new Dictionary<int,string>();
    static BsSourceCodec() {
        using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("mdec-vlc.txt"))
        using(var reader=new StreamReader(stream,Encoding.ASCII)) {
            string line;
            while((line=reader.ReadLine())!=null) {
                if(line.Length==0||line.StartsWith("#"))continue;
                string[] fields=line.Split(':');int code=Int32.Parse(fields[0]);string bits=fields[1];
                Decode.Add(bits,code);Encode.Add(code,bits);
            }
        }
    }
    static int Bit(byte[] source,int index) {
        int offset=8+(index/16)*2;
        if(offset+1>=source.Length)throw new InvalidDataException("잘린 원본 영상입니다.");
        int word=source[offset]|source[offset+1]<<8;return word>>(15-index%16)&1;
    }
    static int Take(byte[] source,ref int cursor,int count) {
        int value=0;for(int i=0;i<count;i++)value=(value<<1)|Bit(source,cursor++);return value;
    }
    static int Signed10(int value){return (value&512)!=0?value-1024:value;}
    static Block[] Parse(byte[] data,int count) {
        if(data.Length<8||BitConverter.ToUInt16(data,6)!=2)throw new InvalidDataException("지원하지 않는 원본 영상 형식입니다.");
        Block[] blocks=new Block[count];int cursor=0;
        for(int b=0;b<count;b++) {
            int start=cursor;int[] coeff=new int[64];coeff[0]=Signed10(Take(data,ref cursor,10));int index=0;
            while(true) {
                string prefix="";int code=0;bool end=false;
                while(true) {
                    prefix+=Take(data,ref cursor,1)==0?"0":"1";
                    if(prefix=="10"){end=true;break;}
                    if(prefix=="000001"){code=Take(data,ref cursor,16);break;}
                    if(Decode.TryGetValue(prefix,out code))break;
                    if(prefix.Length>24)throw new InvalidDataException("잘못된 원본 영상 VLC입니다.");
                }
                if(end)break;index+=(code>>10)+1;
                if(index>=64)throw new InvalidDataException("잘못된 원본 영상 계수입니다.");coeff[index]=Signed10(code&1023);
            }
            blocks[b]=new Block{Coefficients=coeff,Start=start,Length=cursor-start};
        }
        return blocks;
    }
    sealed class Writer {
        readonly MemoryStream output=new MemoryStream();int word,used;
        public Writer(byte[] header){output.Write(header,0,8);}
        public void Put(int bit){word=(word<<1)|bit;if(++used==16){output.WriteByte((byte)word);output.WriteByte((byte)(word>>8));word=used=0;}}
        public void Value(int value,int count){for(int i=count-1;i>=0;i--)Put(value>>i&1);}
        public void Bits(string bits){foreach(char c in bits)Put(c=='1'?1:0);}
        public byte[] Finish(){if(used!=0)throw new InvalidDataException("영상 비트 정렬 오류입니다.");return output.ToArray();}
    }
    public static byte[] Apply(byte[] original,MdecEdit edit) {
        Block[] blocks=Parse(original,edit.blocks.Length);byte[] header=new byte[8];Array.Copy(original,header,8);
        for(int i=0;i<edit.header.Length;i+=2)header[edit.header[i]]=(byte)edit.header[i+1];
        var writer=new Writer(header);
        for(int b=0;b<blocks.Length;b++) {
            Block block=blocks[b];int[] changes=edit.blocks[b];
            if(changes==null){for(int i=0;i<block.Length;i++)writer.Put(Bit(original,block.Start+i));continue;}
            int[] coeff=block.Coefficients;
            for(int i=0;i<changes.Length;i+=2)coeff[changes[i]]=checked(coeff[changes[i]]+changes[i+1]);
            foreach(int n in coeff)if(n< -512||n>511)throw new InvalidDataException("영상 계수 범위 오류입니다.");
            writer.Value(coeff[0]&1023,10);int zeros=0;
            for(int i=1;i<64;i++) {
                if(coeff[i]==0){zeros++;continue;}
                int code=(zeros<<10)|(coeff[i]&1023);string bits;
                if(Encode.TryGetValue(code,out bits))writer.Bits(bits);else{writer.Bits("000001");writer.Value(code,16);}zeros=0;
            }
            writer.Bits("10");
        }
        writer.Bits(edit.tail);byte[] result=writer.Finish();
        if(result.Length!=edit.stream_length)throw new InvalidDataException("영상 길이 검증에 실패했습니다.");return result;
    }
}

public static class CdChecksums {
    static readonly uint[] Edc=new uint[256];static readonly byte[] F=new byte[256],B=new byte[256];
    static CdChecksums(){for(int i=0;i<256;i++){uint v=(uint)i;for(int b=0;b<8;b++)v=(v>>1)^((v&1)!=0?0xD8018001U:0);Edc[i]=v;F[i]=(byte)((i<<1)^((i&128)!=0?0x11D:0));}for(int i=0;i<256;i++)B[i^F[i]]=(byte)i;}
    static byte[] Ecc(byte[] sector,int majorCount,int minorCount,int majorMult,int minorInc) {
        int size=majorCount*minorCount;byte[] result=new byte[majorCount*2];
        for(int major=0;major<majorCount;major++) {
            int index=((major>>1)*majorMult+(major&1))%size;byte a=0,b=0;
            for(int minor=0;minor<minorCount;minor++){byte v=sector[12+index];index=(index+minorInc)%size;a^=v;b^=v;a=F[a];}
            a=B[F[a]^b];result[major]=a;result[major+majorCount]=(byte)(a^b);
        }
        return result;
    }
    // Preserve R152's existing sector bytes exactly, including its checksum
    // convention. This packaging update does not alter the game image.
    public static void RebuildR152(byte[] sector) {
        if(sector.Length!=2352||sector[15]!=2||(sector[18]&32)!=0)throw new InvalidDataException("지원하지 않는 섹터 형식입니다.");
        uint edc=0;for(int i=16;i<2072;i++)edc=(edc>>8)^Edc[(edc^sector[i])&255];
        Array.Copy(BitConverter.GetBytes(edc),0,sector,2072,4);
        Array.Copy(Ecc(sector,86,24,2,86),0,sector,2076,172);Array.Copy(Ecc(sector,52,43,86,88),0,sector,2248,104);
    }
}
