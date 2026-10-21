perfectacle님([https://blog.naver.com/perfectacle/220824102818](https://blog.naver.com/perfectacle/220824102818))의 sfc판 한글패치를 기초로 제작된 한글패치입니다. 흔쾌히 허락해주셔서 진심으로 감사드립니다!!!

1.1패치로 업그레이드 하셨는데 그전 작업물로 작업한거라 1.1버전의 개선점은 반영되지 않았습니다.

kamayoru81님, 감사합니다! 게임 분석과 검수 작업에 도움주시고 앞으로도 개선에 힘써주시기로 하셨습니다!

전... 코덱스 갈군거 밖에 한게 없습니다ㅠ 두분 진심으로 감사드립니다

플레이에 큰 지장이 없는것만 확인했습니다. 혹시 문제 발견하시면 issue에 제보 부탁드립니다.

/////아직 주인공 이름 변경은 불완전합니다. 디폴트 이름으로 진행하시거나, 차후 개선패치를 기다려주세요///
# 제절초 소생편 — PlayStation 한글패치


**공개 버전 1.0.1 / 게임 빌드 R152**

PlayStation용 《제절초 소생편》의 비공식 한글패치입니다. 본문과 선택지, 타이틀·메뉴를 한글로 즐길 수 있도록 작업했습니다. Windows 패처에서 보유한 일본판 원본 BIN을 선택하면 적용할 수 있습니다.

[한글패치 다운로드](https://github.com/ayaneros-eng/otogirisou-ps1-korean-patch/releases/latest)

## 1.0.1 배포 구조 개선

게임 내용은 R152와 바이트 단위로 같습니다. 번역·영상 품질·게임 진행을 유지하며 원본, 세이브와 에뮬레이터 설정을 변경하지 않습니다.

영상 275프레임과 BS 정지 이미지 6개는 이용자의 원본 BIN에서 읽어 수정분을 적용합니다. 완성된 영상·이미지 비트스트림과 수정 섹터 전체를 배포하던 구조를 제거했습니다. 적용 후 전체 BIN의 SHA-256을 검사합니다. [형식과 재현 방법](SOURCE_PATCH_FORMAT.md), [실제 잔존 데이터 검사](COPYRIGHT_AUDIT.json)를 참고하세요.

## 실제 한글 플레이 화면

보존된 실제 실기 검수 화면 10장입니다. 타이틀은 최종 R152이며, 본문·메뉴 예시는 R149–R151 검수 당시 촬영한 화면입니다. 게임 배포본은 R152입니다.

| 한글 타이틀 (R152) | 초반부 인물 묘사 |
|---|---|
| ![한글 타이틀 (R152)](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/01-title.png) | ![초반부 인물 묘사](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/02-opening.png) |

| 산길의 본문 | 본문 대화 |
|---|---|
| ![산길의 본문](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/03-dialogue.png) | ![본문 대화](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/04-story.png) |

| 이름 확인 화면 | 게임 중 메뉴 |
|---|---|
| ![이름 확인 화면](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/05-book.png) | ![게임 중 메뉴](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/06-menu.png) |

| 책 선택 | 조작 설명 |
|---|---|
| ![책 선택](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/07-explanation.png) | ![조작 설명](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/08-controls.png) |

| 메모리카드 슬롯 | 선택한 이야기 |
|---|---|
| ![메모리카드 슬롯](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/09-options.png) | ![선택한 이야기](https://raw.githubusercontent.com/ayaneros-eng/otogirisou-ps1-korean-patch/screenshots/10-selected-book.png) |

## 가장 쉬운 적용 방법 — Windows


1. [최신 릴리스](https://github.com/ayaneros-eng/otogirisou-ps1-korean-patch/releases/latest)에서 **Otogirisou_Korean_Patch_v1.0.1_Windows.zip**을 받아 압축을 풉니다.
2. **Otogirisou_Korean_Patcher.exe**를 실행하고 가지고 있는 **일본판 원본 BIN**을 선택합니다.
3. **패치 시작**을 누릅니다. 완성되면 출력 폴더의 **Otogirisou_KO_R152.cue**를 에뮬레이터에서 엽니다.


Python 설치나 명령어 입력이 필요 없습니다. 패치할 때 인터넷 연결도 필요 없습니다. 원본 파일은 변경하지 않으며, 이미 있는 출력 파일을 덮어쓰지 않습니다. BIN과 CUE는 함께 보관하세요.


**원본 게임과 BIOS는 제공하지 않습니다.** 직접 보유한 일본판 디스크 이미지를 준비하세요. 압축 파일·CHD·ISO·SFC 파일은 이 패처의 입력이 아닙니다.


## 지원하는 원본


| 항목 | 값 |
|---|---|
| 게임 | Sound Novel Evolution 1 - Otogirisou - Sosei-hen (Japan) |
| 플랫폼 / 시리얼 | PlayStation / SLPS-01645 |
| BIN 크기 | 712,192,656바이트 |
| 원본 SHA-256 | `81a130ca6daacf7bf60f2808bb20262e274477ecbfe4ffdec739f00017db58f8` |
| 완성본 SHA-256 | `ff7fd8379be4f342d18008fedf19ca13a2ca3dbcd1cd510284e387341f0cfb5c` |


다른 덤프나 이미 패치한 파일이면 원본 검사에서 중단합니다. 강제로 적용하지 않습니다.


## 현재 범위와 알려진 사항


- 본문, 메뉴와 타이틀에 한글패치를 적용했습니다. 제작 크레딧의 원문 이름·회사명 표기는 유지했습니다.
- 상단 타이틀 문구 잘림, UI 글자 하단, 본문 쉼표·마침표 위치를 수정했습니다.
- 이름 입력의 버벅임과 자음·모음 조합 입력은 추후 과제입니다. 현재는 기존 입력 방식을 사용합니다.
- 시작할 때 ‘여름의 해질녘’, ‘산길은 좁고 구불구불하다’, ‘나미의 옆모습은’ 등 도입부가 달라지는 것은 원본의 난수 선택입니다. 같은 도입부가 연속으로 나올 수 있습니다.
- R152에서 모든 엔딩을 다시 완주한 검수는 아닙니다. 이전 버전의 세이브스테이트는 사용하지 말고 메모리카드 저장을 이용하세요.


문제가 있으면 [Issues](https://github.com/ayaneros-eng/otogirisou-ps1-korean-patch/issues)에 에뮬레이터 이름·버전, 패치 버전, 발생 장면, 재현 순서와 가능하면 스크린샷을 남겨 주세요. 원본 게임 파일이나 BIOS는 업로드하지 마세요.


## 패처를 직접 만들기


이 저장소에는 **차분 패치와 패치 적용 도구의 소스**를 공개합니다. 원본·패치 완료 게임 이미지, BIOS, 개인 세이브와 내부 검수 덤프는 포함하지 않습니다.


Windows에서 저장소 ZIP을 풀고 **build.cmd**를 실행하면 `Otogirisou_Korean_Patcher.exe`가 생성됩니다. Windows의 .NET Framework C# 컴파일러를 사용하며 별도 패키지 다운로드는 없습니다. GUI 실행에는 .NET Framework 4.5 이상이 필요합니다.


`patch.json`은 원본·완성본·패치 파일의 크기와 해시를 고정합니다. `Patcher.cs`가 원본 확인 → 원본을 참조한 수정분 적용 → 완성본 검증을 수행합니다. 에뮬레이터 설정과 세이브 파일은 변경하지 않습니다. 명령줄에서도 같은 엔진을 실행할 수 있습니다.


```powershell
.\Otogirisou_Korean_Patcher.exe --apply "원본.bin" "출력폴더"
```


정상 완료는 종료 코드 0, 오류는 1입니다.


## 권리와 배포


게임의 권리는 각 권리자에게 있습니다. 이 저장소는 비공식 팬 한글패치이며 게임 이미지의 제공·판매를 포함하지 않습니다. perfectacle님의 번역에 대한 감사와 출처 표기를 유지해 주세요. 별도의 광범위한 재배포·상업 이용 허가를 이 README만으로 부여하지 않습니다.



번역·개작에 대한 원게임 저작권자의 권리는 별도로 남습니다. 배포 구조 개선은 법적인 이용 허락이나 모든 권리 문제의 해소를 뜻하지 않습니다.
