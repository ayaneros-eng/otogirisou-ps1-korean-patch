using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Drawing;
using System.Windows.Forms;

[DataContract]
public class PatchInfo {
    [DataMember] public string version;
    [DataMember] public string build;
    [DataMember] public long source_size;
    [DataMember] public long target_size;
    [DataMember] public string source_sha256;
    [DataMember] public string target_sha256;
    [DataMember] public string patch_file;
    [DataMember] public long patch_size;
    [DataMember] public string patch_sha256;
    [DataMember] public string output_stem;
    public static PatchInfo Load() {
        using (Stream s=Assembly.GetExecutingAssembly().GetManifestResourceStream("patch.json"))
            return (PatchInfo)new DataContractJsonSerializer(typeof(PatchInfo)).ReadObject(s);
    }
}

public static class PatchEngine {
    public static string Hex(byte[] b) { return BitConverter.ToString(b).Replace("-", "").ToLowerInvariant(); }
    public static string Hash(Stream f, CancellationToken token, Action<int> progress) {
        long done=0, length=f.Length; byte[] buf=new byte[1024*1024];
        using (SHA256 h=SHA256.Create()) {
            int n;
            while ((n=f.Read(buf,0,buf.Length))>0) {
                token.ThrowIfCancellationRequested(); h.TransformBlock(buf,0,n,buf,0); done+=n;
                if(progress!=null)progress((int)(done*100/Math.Max(length,1)));
            }
            h.TransformFinalBlock(new byte[0],0,0); return Hex(h.Hash);
        }
    }
    public static string Apply(string source, string folder, PatchInfo m, CancellationToken token, Action<int,string> progress) {
        source=Path.GetFullPath(source); folder=Path.GetFullPath(folder);
        string bin=Path.Combine(folder,m.output_stem+".bin"), cue=Path.Combine(folder,m.output_stem+".cue");
        if (String.Equals(source,bin,StringComparison.OrdinalIgnoreCase))throw new IOException("원본과 출력 파일이 같습니다. 다른 출력 폴더를 선택하세요.");
        if (File.Exists(bin)||File.Exists(cue))throw new IOException("출력 파일이 이미 있습니다. 기존 파일은 덮어쓰지 않습니다. 다른 출력 폴더를 선택하세요.");
        byte[] patch;
        using(Stream s=Assembly.GetExecutingAssembly().GetManifestResourceStream("patch.otopatch")) {
            if(s==null||s.Length!=m.patch_size)throw new InvalidDataException("패치 데이터가 손상되었습니다.");
            using(MemoryStream b=new MemoryStream()){s.CopyTo(b);patch=b.ToArray();}
        }
        using(SHA256 h=SHA256.Create())if(Hex(h.ComputeHash(patch))!=m.patch_sha256)throw new InvalidDataException("패치 데이터의 해시가 다릅니다.");
        DeltaDocument delta=SourceDelta.Load(patch,m);
        string temp=null,tempCue=null;
        try {
            using(FileStream input=new FileStream(source,FileMode.Open,FileAccess.Read,FileShare.Read)) {
                if(input.Length!=m.source_size)throw new InvalidDataException("지원하는 일본판 원본 BIN이 아닙니다. README의 원본 정보와 크기를 확인하세요.");
                progress(0,"원본 확인 중");
                string original=Hash(input,token,p=>progress(p*25/100,"원본 확인 중"));
                if(original!=m.source_sha256)throw new InvalidDataException("원본 BIN의 해시가 다릅니다. 이미 패치한 파일이나 다른 덤프에는 적용할 수 없습니다.\r\n\r\n현재 SHA-256: "+original+"\r\n필요한 SHA-256: "+m.source_sha256);
                input.Position=0;Directory.CreateDirectory(folder);
                temp=Path.Combine(folder,".otogirisou-"+Guid.NewGuid().ToString("N")+".partial");
                using(FileStream output=new FileStream(temp,FileMode.CreateNew,FileAccess.ReadWrite,FileShare.None)) {
                    byte[] buffer=new byte[1024*1024];long done=0;int n;
                    while((n=input.Read(buffer,0,buffer.Length))>0) {
                        token.ThrowIfCancellationRequested();output.Write(buffer,0,n);done+=n;
                        progress(25+(int)(done*30/m.source_size),"한글패치 생성 중");
                    }
                    SourceDelta.Apply(input,output,delta,token,progress);
                    output.Flush();output.Position=0;
                    string result=Hash(output,token,p=>progress(80+p*20/100,"완성본 확인 중"));
                    if(output.Length!=m.target_size||result!=m.target_sha256)throw new InvalidDataException("완성본 검증에 실패했습니다. 생성 파일은 배포하지 않습니다.");
                }
            }
            token.ThrowIfCancellationRequested();
            tempCue=temp+".cue";
            using(FileStream f=new FileStream(tempCue,FileMode.CreateNew,FileAccess.Write)) {
                byte[] text=new UTF8Encoding(false).GetBytes("FILE \""+Path.GetFileName(bin)+"\" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n");f.Write(text,0,text.Length);
            }
            File.Move(temp,bin);temp=null;File.Move(tempCue,cue);tempCue=null;
            progress(100,"한글패치 완성");return cue;
        } finally {
            foreach(string p in new[]{temp,tempCue})if(p!=null&&File.Exists(p))File.Delete(p);
        }
    }
}

public sealed class PatchForm:Form {
    readonly PatchInfo meta=PatchInfo.Load();
    readonly TextBox source=new TextBox(), output=new TextBox();
    readonly Button choose=new Button(), dest=new Button(), apply=new Button(), cancel=new Button();
    readonly Label status=new Label();readonly ProgressBar bar=new ProgressBar();
    CancellationTokenSource cts;string finished;
    public PatchForm() {
        Text="제절초 소생편 한글패치 "+meta.version+" ("+meta.build+")";ClientSize=new Size(690,305);
        Font=new Font("맑은 고딕",10);AutoScaleMode=AutoScaleMode.Dpi;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
        Label heading=new Label{Text="일본판 원본 BIN을 선택하고 ‘패치 시작’을 누르세요.",AutoSize=true,Left=20,Top=18};Controls.Add(heading);
        Controls.Add(new Label{Text="원본 BIN",Left=20,Top=65,Width=90});source.SetBounds(110,60,440,30);choose.Text="선택…";choose.SetBounds(560,59,105,32);
        Controls.Add(new Label{Text="출력 폴더",Left=20,Top=110,Width=90});output.SetBounds(110,105,440,30);dest.Text="변경…";dest.SetBounds(560,104,105,32);
        bar.SetBounds(20,155,645,22);status.SetBounds(20,185,645,32);status.Text="원본은 변경하지 않습니다. 완성된 CUE 파일로 게임을 실행하세요.";
        apply.Text="패치 시작";apply.SetBounds(400,240,130,38);cancel.Text="취소";cancel.SetBounds(540,240,125,38);cancel.Enabled=false;
        Controls.AddRange(new Control[]{source,output,choose,dest,bar,status,apply,cancel});
        choose.Click+=delegate{using(OpenFileDialog f=new OpenFileDialog{Title="일본판 원본 BIN 선택",Filter="BIN 이미지 (*.bin)|*.bin|모든 파일 (*.*)|*.*"})if(f.ShowDialog(this)==DialogResult.OK){source.Text=f.FileName;if(String.IsNullOrWhiteSpace(output.Text))output.Text=Path.Combine(Path.GetDirectoryName(f.FileName),"제절초_한글패치_출력");}};
        dest.Click+=delegate{using(FolderBrowserDialog f=new FolderBrowserDialog{Description="완성본을 저장할 폴더",SelectedPath=output.Text})if(f.ShowDialog(this)==DialogResult.OK)output.Text=f.SelectedPath;};
        apply.Click+=async delegate{await StartPatch();};cancel.Click+=delegate{if(cts!=null)cts.Cancel();};
        FormClosing+=delegate(object sender,FormClosingEventArgs e){if(cts!=null){cts.Cancel();e.Cancel=true;status.Text="취소 처리 중입니다. 잠시 기다려 주세요.";}};
    }
    void Busy(bool busy){choose.Enabled=dest.Enabled=apply.Enabled=source.Enabled=output.Enabled=!busy;cancel.Enabled=busy;}
    async Task StartPatch(){
        if(!File.Exists(source.Text)||String.IsNullOrWhiteSpace(output.Text)){MessageBox.Show(this,"원본 BIN과 출력 폴더를 선택하세요.");return;}
        cts=new CancellationTokenSource();Busy(true);bar.Value=0;
        var progress=new Progress<Tuple<int,string>>(x=>{bar.Value=Math.Max(0,Math.Min(100,x.Item1));status.Text=x.Item2;});
        string src=source.Text,folder=output.Text;
        try{
            finished=await Task.Run(()=>PatchEngine.Apply(src,folder,meta,cts.Token,(p,s)=>((IProgress<Tuple<int,string>>)progress).Report(Tuple.Create(p,s))));
            string note="완성되었습니다. 실행 파일:\r\n"+finished;
            status.Text="완성: "+finished;MessageBox.Show(this,note,"한글패치 완성",MessageBoxButtons.OK,MessageBoxIcon.Information);
        }catch(OperationCanceledException){status.Text="취소했습니다. 원본은 변경하지 않았습니다.";}
        catch(Exception e){status.Text="패치를 완료하지 못했습니다.";MessageBox.Show(this,e.Message,"패치 확인",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
        finally{cts.Dispose();cts=null;Busy(false);}
    }
}

public static class Program {
    [STAThread] public static int Main(string[] args){
        if(args.Length>0){
            try{
                Console.SetError(new StreamWriter(Console.OpenStandardError(),new UTF8Encoding(false)){AutoFlush=true});
                Console.SetOut(new StreamWriter(Console.OpenStandardOutput(),new UTF8Encoding(false)){AutoFlush=true});
            }catch{}
            try{
                if(args.Length!=3||args[0]!="--apply")return 2;
                string cue=PatchEngine.Apply(args[1],args[2],PatchInfo.Load(),CancellationToken.None,(p,s)=>{});
                try{Console.WriteLine(cue);}catch{}return 0;
            }catch(Exception e){try{Console.Error.WriteLine(e.Message);}catch{}return 1;}
        }
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new PatchForm());return 0;
    }
}
