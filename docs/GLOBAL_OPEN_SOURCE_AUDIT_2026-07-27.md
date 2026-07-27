# インダス文字・世界オープンソース監査

基準日: 2026-07-27

状態: 内部監査版。解読・翻訳の主張ではない。

対象: 公開コーパス、コード、モデル、合成データ、地理データベース、
文字コード・フォント、公開3D資源

## 監査原則

この文書は、[研究台帳](../registry/research_landscape.json)の証拠階層と
権利区分に合わせ、次の四つを分離して判定する。

1. **コードのライセンス**: プログラムを複製・変更・再配布できるか。
2. **入力データと字形の権利**: 写真、図版、転写、符号画像、フォントの
   上流権利が確認できるか。
3. **計算上の再現性**: 版、入力、分割、コード、環境、seed、重みがそろい、
   記載結果を再計算できるか。
4. **科学的妥当性**: 同一遺物群の漏洩、循環評価、仮説ラベルの真値化を避け、
   強い帰無モデルと未見資料に耐えるか。

公開URLがあること、GitHubやHugging Faceに置かれていること、論文が
CC BYであることは、これら四条件を同時に満たすことを意味しない。

本監査では公開物を読み取り専用で確認した。外部への連絡、データ利用許諾の照会、
非公開資料の取得は行っていない。「リポジトリを確認できない」「3Dモデルを
見つけられない」という記述は、指定した検索範囲と基準日における
`search_not_found`であり、不存在の断定ではない。

## 総合判定

| 資源 | 固定した版 | コードの権利 | データ・字形の権利 | 再現性 | 本プロジェクトでの判定 |
|---|---|---|---|---|---|
| 外部IndusBench | `5e21125e4f305b42076a6617f8fd2b1ac658be8b` | ライセンスなし | 上流もライセンスなし | 公開分割は読めるが、lockと評価設計に重大な欠陥 | **隔離**。盲検ベンチマークとして不採用 |
| HF合成データ | dataset `e455cfc7e9069ade81ce994b47b7a7533308627e`、models `4f6155bc56be51ae62676c292afc42096a04f9d8` | カード上CC-BY-4.0 | 実資料とPUA字形の上流不明 | 重みと推論コードはあるが、実資料、完全な訓練コード、分割がない | **隔離**。合成研究対象に限定 |
| ASDA | `14bd43147d1421bf13f4f43666175ab5d61a77f7` | CC0-1.0 | 完全データは申請制、画像権利は別 | 現状は静的監査で実行阻害要因あり | **条件付き参照**。コード手法のみ |
| AI-EPIGRAPHY | `30d02d0431ec12a1dea2a10fc9ca52ee0f8bd1b8` | ライセンスなし | 45符号CSVの来歴・再配布条件不明 | UIは追跡可能、学術結果は独立再現不可 | **隔離**。UI参考に限る |
| ivc2tyc | `1ab600eef88c4cf85ad9fc0cfe2d272e73eb4821`、Zenodo `10.5281/zenodo.20755243` | コードMIT | 第三者データは原権利を維持 | 大型成果物あり。ただし依存関係・seed・Colab pathに制約 | **条件付き採用**。視覚手法のみ |
| Nair 2026 | arXiv:2604.17828v1 | 公開コードを確認できず | ICIT/Yajnadevam派生権利不明 | 公開可否の記述が論文内で矛盾 | **追跡**。再現前は結論に使わない |
| Tiwari 2026 | DOI `10.18653/v1/2026.nlp4dh-1.28` | 公開repoを確認できず | 6,579列の権利・版・来歴不明 | 公開予定記述はあるが公開物を確認できず | **追跡**。再現前は結論に使わない |
| MAHSA | 2026-07-27公開サービス | ArchesはOSS | MAHSA内容の包括ライセンスなし | 公開検索は動作。符号列コーパスではない | **リンク採用**。遺跡文脈候補 |
| Kriger–Hunt 2026 | DOI `10.5281/zenodo.19103880` | 添付コードなし | 説明文はCC BY 4.0、metadata rightsはnull | 「code/data添付」と実ファイルが不一致 | **仮説隔離** |
| Unicode / PUA fonts | 下記commit・提案番号 | 資源ごとに異なる | 字形上流と符号対応は別監査 | Unicode正式割当なし、PUA間に互換性なし | **crosswalk必須** |

## 1. 外部の「IndusBench」

対象は
[prabhatchanchal/IndusBench](https://github.com/prabhatchanchal/IndusBench/tree/5e21125e4f305b42076a6617f8fd2b1ac658be8b)
のcommit
`5e21125e4f305b42076a6617f8fd2b1ac658be8b`である。READMEは
「first objective reproducible benchmark」「locked test」と説明し、
3,237列、712符号、68遺跡を掲げる。しかしリポジトリにLICENSEはない。

上流として明記される
[yajnadevam/lipi](https://github.com/yajnadevam/lipi/tree/98b293971422daba0a94f8c54c1aa4952eea3a8a)
の監査commitは
`98b293971422daba0a94f8c54c1aa4952eea3a8a`で、こちらにもLICENSEがない。
上流READMEは独自の音価・翻訳を「provably deciphered」と扱い、
`src/assets/data/inscriptions.csv`、読み、翻訳、フォントについて
一次資料の版・行単位来歴・再配布根拠を示していない。外部IndusBenchの
「same as source corpus」というライセンス記述は、上流が無ライセンスであるため
再利用許可として機能しない。

公開された
[train.json](https://github.com/prabhatchanchal/IndusBench/blob/5e21125e4f305b42076a6617f8fd2b1ac658be8b/split/train.json)と
[test.json](https://github.com/prabhatchanchal/IndusBench/blob/5e21125e4f305b42076a6617f8fd2b1ac658be8b/split/test.json)
を独立集計すると、corpus 3,237列、train 2,664列、test 573列だった。
完全一致符号列のtrain/test重複は0だが、これはcorpus builderが分割前に
`sign_sequence`だけで最初の一行を残すためである。この処理は同一列が異なる
遺物・場所・媒体で反復する証拠も失う。

一方、末尾の枝番号を落とした同一base IDは43群がtrain/testを跨ぎ、
train側48行、test側45行に現れた。例として`1227.1`と`1227.3`、
`2844.1/.3/.5`と`2844.2/.4/.6`が別側へ分かれる。同じ非空`cisi`値も
43件が両側に現れる。行単位の層化分割であり、同一遺物、印章と印影、
枝番号、同型群を遮断した盲検分割ではない。

公開
[lock.json](https://github.com/prabhatchanchal/IndusBench/blob/5e21125e4f305b42076a6617f8fd2b1ac658be8b/split/lock.json)
のchecksumはtrain/test ID配列だけを対象とし、入力内容、評価器、環境を
固定しない。
[run_benchmark.py](https://github.com/prabhatchanchal/IndusBench/blob/5e21125e4f305b42076a6617f8fd2b1ac658be8b/run_benchmark.py)
は`locked=true`を確認して
保存済みchecksumを表示するだけで、実データから再計算して不一致時に停止しない。
test JSON自体も公開されている。

総合スコアDCSにも、少なくとも次の検証課題がある。

- 一様予測のtieで`n_higher=0`となり、grammar model rankingが1.0になり得る。
- reproducibilityが全モデルで1.0に固定される。
- simplicityが実測量ではなくモデル名カテゴリで固定される。
- phoneme候補は同じ公開コーパスから構築され、未見資料による外部支持ではない。

したがって台帳候補
`software-prabhatchanchal-indusbench-2026`はTier D、
`status=disputed`、`falsification.applicability=audit_only`、
`rights_status=unknown`、`redistribution=false`とする。
本プロジェクトの正式な盲検ベンチマーク、順位表、学習データには採用しない。

## 2. Hugging Faceの合成データとモデル

確認した公開物は次の三点である。

- [hellosindh/indus-script-synthetic](https://huggingface.co/datasets/hellosindh/indus-script-synthetic/tree/e455cfc7e9069ade81ce994b47b7a7533308627e):
  commit `e455cfc7e9069ade81ce994b47b7a7533308627e`、カード上CC-BY-4.0。
- [hellosindh/indus-script-models](https://huggingface.co/hellosindh/indus-script-models/tree/4f6155bc56be51ae62676c292afc42096a04f9d8):
  commit `4f6155bc56be51ae62676c292afc42096a04f9d8`、カード上CC-BY-4.0。
- [hellosindh/indus-script-demo](https://huggingface.co/spaces/hellosindh/indus-script-demo/tree/4a8c284252ab119a80a2b0e27af810a157b650fc):
  commit `4a8c284252ab119a80a2b0e27af810a157b650fc`、カード上CC-BY-4.0。

dataset cardは「実在する3,310銘文」で複数モデルを訓練し、5,000合成列を生成、
その合成列を加えて再訓練したと説明する。公開されているのは最終
`synthetic_indus_5k.csv`、符号索引、重み、推論コードであり、
元の3,310列、その行単位来歴、遺物群分割、完全な訓練パイプライン、
固定seed・環境は含まれない。

生成モデルの候補を、同じ実資料で訓練したBERT、n-gram、ELECTRAで採点し、
選別した合成列を再び訓練へ加えているため、採点は独立評価ではない。
学習対象と完全一致した752列を「strongest validation」とする説明も、
外部妥当性より記憶・過学習を検査すべき事象である。

記載と公開ファイルにも不整合がある。

- READMEは実資料の語彙を641符号とするが、`reference/sign_index.json`は
  `total_signs=715`で715項目を持つ。
- READMEのFiles節はJSONLを案内するが、監査commitの公開データ本体はCSVである。
- PUA glyph、T番号、実資料の出典・inventory version・crosswalkが示されない。

CC-BY-4.0表示は、公開者自身が生成した合成列の利用条件として記録できるが、
出典不明の実資料、既存転写、PUA字形の権利まで解決したとは判定しない。
台帳候補
`dataset-hf-hellosindh-indus-script-synthetic-2026`はTier D、
`status=disputed`、合成データ限定、`audit_only`とする。
符号頻度、実資料分布、解読、未見評価の真値には使わない。

Hugging Faceの`indus-script`タグでは、ほかに
[Zer0pa/Indus-Valley-lane-state](https://huggingface.co/datasets/Zer0pa/Indus-Valley-lane-state)
と
[junafinity/p316-p147-p217-indus-branch-audit-20260609](https://huggingface.co/datasets/junafinity/p316-p147-p217-indus-branch-audit-20260609)
も確認した。前者は権利で遮断した資料を除外した運用・復旧snapshotで、
完全コーパスではない。後者自身も厳密結果を`NOT LICENSED`、
機能仮説をconfidence 0.36と記載する。いずれも一次コーパスや
解読ground truthには採用しない。

## 3. ASDAとAI-EPIGRAPHY

### ASDA

[DM-BiCLab/Deep-Learning-in-Archiving-Indus-Script-and-Motif-Information](https://github.com/DM-BiCLab/Deep-Learning-in-Archiving-Indus-Script-and-Motif-Information/tree/14bd43147d1421bf13f4f43666175ab5d61a77f7)
の監査commitは
`14bd43147d1421bf13f4f43666175ab5d61a77f7`で、リポジトリのコードは
CC0-1.0である。対応論文は
[Deep Learning in Archiving Indus Script and Motif Information](https://doi.org/10.5334/jcaa.175)
で、研究台帳の`paper-dixit-2025-asda`と対応する。

完全な研究データはREADME上「著者へ申請」で、公開repoにはsample画像しかない。
モデル重み、厳密な依存関係lock、元画像ごとの所蔵・出典・利用条件もない。
CC0は第三者画像の権利を上書きしない。

静的監査では次を確認した。

- コード内に`#Change to data path`が残る。
- `Training and Validation Phase/MI.py`のvalidation pathに引用符の不整合がある。
- `mobileNet.ipynb`は名称・説明と異なり`ResNet50`を生成する。
- `history_data['accuracy']`など、Keras `History.history`を経由しない参照がある。
- cross-validation notebookは既存train/validation/testを連結して再分割し、
  遺物・印章/印影・同型群を遮断しない。最終評価も最後のfoldのモデルに依存する。

研究台帳ではコードの`license_id=CC0-1.0`と、完全データの
`permission_required`・画像権利未確認を分離する。現状の判定は
`execution_readiness=fails_static_audit`相当であり、論文値を
独立再現済みとはしない。

### AI-EPIGRAPHY

[atulsharma0071/indiahci2025](https://github.com/atulsharma0071/indiahci2025/tree/30d02d0431ec12a1dea2a10fc9ca52ee0f8bd1b8)
の監査commitは
`30d02d0431ec12a1dea2a10fc9ca52ee0f8bd1b8`で、LICENSEはない。
READMEが示す論文DOIは
[10.1145/3768633.3770145](https://doi.org/10.1145/3768633.3770145)である。

同梱CSVは45行で、Vats、Marshall、S. R. Rao由来とされる候補を混在させる。
「reading」「meaning」は合意済みの音価・語義ではなく、
特定の解読仮説である。ランダムな80/20分割で候補ラベルを分類し、
表示confidenceも真の解読確率ではない。

UI構成や探索画面は参考にできるが、コード・CSVを再配布せず、
意味ラベルを教師データにしない。台帳候補
`software-ai-epigraphy-indiahci2025`はTier D、
`rights_status=unknown`、`permitted_use=link_only`、
`falsification.applicability=audit_only`とする。

## 4. ivc2tyc

[oohalakkadi/ivc2tyc](https://github.com/oohalakkadi/ivc2tyc/tree/1ab600eef88c4cf85ad9fc0cfe2d272e73eb4821)
はtag v1.0.0相当、監査commit
`1ab600eef88c4cf85ad9fc0cfe2d272e73eb4821`で、コードはMITである。
PCI Archaeologyの推薦記録は
[10.24072/pci.archaeo.100711](https://doi.org/10.24072/pci.archaeo.100711)、
長期アーカイブの正本は
[Zenodo 10.5281/zenodo.20755243](https://doi.org/10.5281/zenodo.20755243)である。
[Zenodo 21158710](https://zenodo.org/records/21158710)はGitHub release由来の
補助snapshotとして区別する。

正本Zenodoにはdatasets、results、code、embeddings、trained modelsがある。
`ivc2tyc-code-v1.0.0.zip`のSHA-256は
`7c9449a38d711c3d5572dfb8559d63ebc09e6683b1516b2ae78d3d1e9ea270f1`、
MD5は`a18c9741d732279bd8dc5e5615ee8155`である。
一方、Zenodo record-level licenseはMITだが、READMEは第三者データをMITで
再許諾せず原ライセンスを維持すると明記し、新規生成出力はCC BY 4.0予定とする。
したがってファイル種別ごとの権利判定が必要である。

GitHub treeには`datasets/indus/`配下の715 JPEGと`reference/indus/ICIT.html`がある。
`datasets.ipynb`はICITページを解析し、`https://www.indus.epigraphica.de/`から
画像を取得する処理を含む。しかし715画像ごとの遺物ID、出典、原ライセンス、
許諾根拠を列挙したmanifestはない。MITやZenodo metadataを、これら画像の
再配布許可として扱わない。

再現面では大型成果物が保存されている点は有用だが、
requirementsは厳密にpinされず、notebookに歴史的Colab/Google Drive pathが残り、
訓練は確率的である。視覚埋め込み、安定性解析、成果物保存の方法は
条件付き採用できる。Indus一次銘文コーパスとしては採用せず、
視覚的近さを歴史的接触、系統関係、同一言語・音価の証拠に変換しない。

台帳候補`software-ivc2tyc-1.0.0`には、コードMIT、生成出力CC BY 4.0予定、
第三者データ`source_license_applies`、715 ICIT画像`rights_pending`を
別フィールドで記録する。

## 5. Nair 2026とTiwari 2026

### Nair 2026

[arXiv:2604.17828v1](https://arxiv.org/abs/2604.17828)は2026-04-20提出の
*How Non-Linguistic Is the Indus Sign System? A Synthetic-Baseline Scorecard*
で、DOIは
[10.48550/arXiv.2604.17828](https://doi.org/10.48550/arXiv.2604.17828)である。

抄録は「All code and data are publicly available」とする一方、
[本文HTML](https://arxiv.org/html/2604.17828)のData and Code Availability節は、
pipeline、corpus、scriptsを対応著者への申請で提供し、
採択後にpublic repositoryへ公開すると記す。arXiv recordには
公開repo URLがない。基準日の限定検索でも対応repoを特定できなかったが、
これは将来の公開や未索引repoの不存在を意味しない。

研究台帳`preprint-nair-2026-scorecard`はTier D、
`status=partially_verified`を維持し、
「availability statement internally inconsistent」
「exact independent reproduction currently blocked」を追記する。
ICIT/Yajnadevam派生1,916列の版、重複除去、符号正規化、権利を確認するまで
結果を正式ベンチマークへ移さない。

### Tiwari 2026

[ACL Anthology 2026.nlp4dh-1.28](https://aclanthology.org/2026.nlp4dh-1.28/)
のDOIは
[10.18653/v1/2026.nlp4dh-1.28](https://doi.org/10.18653/v1/2026.nlp4dh-1.28)である。
論文のData Availability節は、6,579列のprocessed datasetとanalysis scriptsを
出版時にopen repositoryへ公開すると記す。基準日にはAnthology recordから
具体的repoへリンクされておらず、題名、著者名、6,579という件数を用いた
限定検索でも対応repoを特定できなかった。

CC-BY-4.0は論文本文の再利用条件として記録できるが、未公開の銘文転写、
元図録、画像、コードの権利を自動的に与えない。研究台帳
`paper-tiwari-2026-statistical-structure`はTier D、
`status=partially_verified`を維持し、データ・コードの
`availability=not_found_as_of_2026-07-27`を追加する。

再現時には、6,579列の出典・重複定義、同一遺物群を遮断したsplit、
表4の実資料perplexity 2.60と改変列1.10、1.39、2.42の解釈を先に監査する。

## 6. MAHSA

University of Cambridgeの
[MAHSA project page](https://www.arch.cam.ac.uk/research/projects/current-projects/mapping-archaeological-heritage-south-asia)
は、Archesを用いるopen-access geospatial databaseの構築を説明する。
基準日には
[MAHSA live database](https://databasemahsa.org/en/)が実際に応答し、
[公開検索endpoint](https://databasemahsa.org/en/search/resources)は
`total_results=1804`を返した。これは基準日時点の既定検索応答であり、
1,804件すべてが遺跡、インダス期、または文字資料であるという意味ではない。
既定結果にはhistoric map recordsが含まれる。

Archesが
[open-source platform](https://www.archesproject.org/)であることと、
MAHSAのレコード、地図、写真、衛星派生物、exportが一つのオープンライセンスで
提供されることは別である。MAHSA画面のTerms & ConditionsとPrivacy Policyは
基準日に`href="#"`で、内容固有のライセンスを確認できなかった。

研究台帳`project-cambridge-mahsa-phase2`のTier A、
`status=verified`はプロジェクトとサービスの存在について維持する。
データは`rights_status=unknown`、`permitted_use=link_only`とし、
遺跡・地理・歴史地図の文脈候補に限定する。符号列、音価、翻訳を供給する
一次コーパスとしては扱わない。

## 7. Kriger–Hunt 2026

[Zenodo 10.5281/zenodo.19103880](https://zenodo.org/records/19103880)は
*Positional constraints, sequence uniqueness, and stroke numerals in Indus seal
inscriptions from Mohenjo-Daro: a statistical analysis*で、2026-03-19公開、
著者はBoris KrigerとTreasure A. Huntである。mayigの179印章、
1,003トークン、182符号を使い、登録コード機能を主張する。

record descriptionは「Code and data are fully open」「Supplementary code:
included as attachment」「License: CC-BY 4.0」とする。しかしAPIで確認できる
実ファイルはPDF
`Positional_constraints_sequence_uniqueness_stroke_numerals_Indus_Mohenjo-Daro_v5_AUTHOR.pdf`
一件だけで、MD5は`3d9f3f0dceb9d19899dbed88733ec79a`である。
record metadataの`rights`はnullだった。

したがって公開説明だけからコード再現可能とは判定しない。
台帳entry `preprint-kriger-hunt-2026-functional`はTier Dの
自己公開プレプリント、`status=disputed`、`audit_only`とする。
位置・一意性の観測と「登録コード」という機能推定を分離し、
コード、生成表、帰無モデル、独立コーパスが公開されるまで
機能結論を採用しない。

## 8. Unicode、フォント、符号ID

[Unicode SMP roadmap](https://www.unicode.org/roadmaps/smp/)はIndusを
括弧付きの暫定項目として掲載する。roadmap自身がinformativeかつ
provisionalで、範囲は変更され得ると明記する。リンク先の正式提案は
[ISO/IEC JTC1/SC2/WG2 N1959](https://www.unicode.org/L2/L1999/n1959.pdf)
で、1999-01-29付、386字、提案範囲U+13700–U+13881である。
これは現在のUnicode Standardに割当済みのIndus blockではない。

確認した公開フォント・表示資源は次のとおり。

| 資源 | 監査commit | 表示ライセンス | 主な制約 |
|---|---|---|---|
| [decipher-indus/font](https://github.com/decipher-indus/font/tree/c8a02a373a7cb449d1fe1f03e781e4510f6bb201) | `c8a02a373a7cb449d1fe1f03e781e4510f6bb201` | GPL-3.0 | SFD/TTF/WOFF2あり。PUAはU+E000以降だが、inventory version・符号対応表・字形来歴が不足 |
| [exceptnull/indus-character-map](https://github.com/exceptnull/indus-character-map/tree/344b76a9292726a58ed1db3cea0b09510b3fba01) | `344b76a9292726a58ed1db3cea0b09510b3fba01` | top-level MIT | 上記GPLフォントを含むため、フォント部分のライセンス表示・source提供を別確認する必要 |
| [ram-g-athreya/indus-keyboard](https://github.com/ram-g-athreya/indus-keyboard/tree/740ee125bb8b79abc166d514ce6241a3b690c14a) | `740ee125bb8b79abc166d514ce6241a3b690c14a` | Apache-2.0 | Yajnadevam由来のフォント・対応で、一次inventoryと独自解読候補を分離できない |
| [cluesurf/mark](https://github.com/cluesurf/mark/tree/a3f00c851baebd5c7a1c1a8996991a42c53fa276) | `a3f00c851baebd5c7a1c1a8996991a42c53fa276` | OFL-1.1 | Indus packageのfont、SVG、mappingは未構築のplaceholder |

フォントのライセンスは、符号分類の正しさ、元図版・字形の権利、
別フォントとのPUA互換性を保証しない。正本データではraw PUA codepointを
符号identityにせず、少なくとも
`inventory_id`、`inventory_version`、`sign_id`、`glyph_variant_id`、
`font_revision`、`crosswalk_status`を保持する。

台帳entry `official-unicode-indus-roadmap-2026`には、暫定roadmap項目、
提案番号N1959、386字、正式割当なしとして記録する。フォントは
software entryとして個別ライセンスを記録し、字形データの権利を別項目にする。

## 9. 一次画像と3D探索

公式・一次性を優先し、
[Smithsonian 3D](https://3d.si.edu/)、
[Open Heritage 3D](https://openheritage3d.org/)、
[Penn Museum公式Sketchfab](https://sketchfab.com/pennmuseum)、
British Museum関連検索を確認した。

Penn Museum公式アカウントには
[Harappan figurine 67-29-7](https://sketchfab.com/3d-models/harappan-figurine-3c4ee2c8f5e5499ca41551e97e7cd4f0)
があるが、文字入り遺物ではない。British Museumの印章を題材にする
[Sketchfab model](https://sketchfab.com/3d-models/seal-mohenjo-daro-british-museum-ea4f061f0a4e4d08b67ac1926877347c)
も検索結果に現れるが、博物館公式upload、原物scan、download licenseを
同時に確認できない第三者投稿だった。

今回の検索範囲では、次をすべて満たす文字入りIndus遺物3Dを確認できなかった。

- 公式所蔵機関または発掘主体による公開。
- accession/object IDと原物記録への恒久リンク。
- geometryとtextureの再利用ライセンス。
- scan方法、縮尺、向き、印章/印影の区別。
- geometry・textureの固定hash。

これは該当3D資源が世界に存在しないという断定ではない。
台帳には`search_not_found_as_of_2026-07-27`と検索先を記録し、
第三者制作物を一次計測や学習画像へ入れない。将来の採用には
object ID、scan provenance、rights、scale、orientation、hashを必須にする。

## 採用・隔離ルール

| 区分 | 今回該当するもの | 許可する利用 |
|---|---|---|
| 採用可能 | 公式DOI・landing page、commit metadata、明示ライセンスのコード | 引用、来歴台帳、権利範囲内の方法監査 |
| 条件付き採用 | ASDAのCC0コード、ivc2tycのMITコードと生成成果物 | 入力を権利確認済みに差し替え、環境を固定して再実行 |
| リンクのみ | MAHSA records、公開論文、権利未確認の転写・図版 | URL、書誌、観察候補の記録 |
| 隔離 | 外部IndusBench、HF合成列、AI-EPIGRAPHY意味ラベル、ICIT由来画像、Yajnadevam派生データ | 監査・反証だけ。学習、正式評価、再配布をしない |
| 不採用 | 出典不明画像、第三者3D、PUAだけで同定された符号 | 正本データ、ground truth、盲検testには使用しない |

隔離は内容が必ず誤りだという意味ではない。権利、来歴、独立評価のいずれかが
欠けるため、正式な証拠経路へ混ぜないという運用判断である。

## 研究台帳への反映

2026-07-27監査では、既存entryを次のように更新済みである。

- `paper-dixit-2025-asda`: code CC0-1.0、full data request-only、
  source-image rights unknown、static audit failureを分離。
- `preprint-nair-2026-scorecard`: 抄録とData Availability節の矛盾、
  public repo URL未確認、exact reproduction blockedを追記。
- `paper-tiwari-2026-statistical-structure`: dataset/code
  `not_found_as_of_2026-07-27`、論文CC BYとコーパス権利を分離。
- `project-cambridge-mahsa-phase2`: live DB URL、公開search endpoint、
  content licence未確認、link-onlyを追記。

新規登録済みentryは次のとおり。

- `software-prabhatchanchal-indusbench-2026`
- `dataset-hf-hellosindh-indus-script-synthetic-2026`
- `software-ai-epigraphy-indiahci2025`
- `software-ivc2tyc-1.0.0`
- `preprint-kriger-hunt-2026-functional`
- `official-unicode-indus-roadmap-2026`

フォント四件はこの文書で監査対象として固定したが、個別software entryは
まだ作成していない。将来登録する場合も、確認済みcommitまたはDOI、
アクセス日、コードライセンス、データ権利、上流entry、採用範囲、
反証条件を必須にする。

## 実装状況と次の優先度

以下のP0/P1/P2はこの監査内のpriority番号であり、
`DEVELOPMENT_PLAN_AND_LOG.md`の実装milestone番号とは独立である。

### P0: 誤採用を止める — 2026-07-27実装済み

1. 外部IndusBench、HF合成データ、AI-EPIGRAPHY、Yajnadevam派生物を
   [content-addressed quarantine manifest](../registry/quarantine.json)へ登録し、
   通常のcorpus・training・evaluation loaderから拒否した。
2. `code_license`、`data_rights_status`、`glyph_rights_status`、
   `redistribution`を監査台帳では独立に評価し、通常経路では出典台帳と
   artifact/image rightsを目的別に再検査する。
3. 「blind」「locked」「verified」「ground truth」を、
   公開分割と定義lockに設定できない閉じたschema・semantic ruleを追加した。

### P1: 分割とlockを作り直す — 定義・提出内容層まで実装、blind実行層は未実装

1. 行単位ではなく、遺物ID、base ID、CISI/Mahadevan/ICIT crosswalk、
   印章/印影、同型・鋳型候補、画像exact/perceptual hashでgroup splitする。
2. corpus bytes、schema、split、隔離表、評価器、`pyproject.toml`、
   `uv.lock`を[public-development definition lock](BENCHMARK_LOCK.md)へ含めた。
   callerが選んだcandidate root直下のcomplete inventoryは
   [local submission content commitment](SUBMISSION_COMMITMENT.md)で固定できる。
   外部/runtime dependency closure、外部custody、hidden companion、
   run/result receiptは未実装である。
3. 定義検証時に全hash、corpus union、member evidence、leakage auditを
   再計算し、不一致時はfail closedにした。
4. 生成名を公開`development.jsonl`へ変更した。最終testは未作成であり、
   将来も外部機関のcustodyなしにblind/finalとは呼ばない。

### P2: 再現と標準化

1. ASDAとivc2tycは権利確認済みの小規模入力へ差し替え、
   dependency lock、seed、CPU/GPU環境、期待出力を固定して再現する。
2. NairとTiwariは公開物の定期差分監視を行い、repo公開後に
   exact corpus lineageとsplitを先に監査する。
3. PUAを正本から排除し、Mahadevan、Wells/ICIT、CISI、各フォント間の
   versioned crosswalkを作る。
4. 3Dは公式所蔵ID・scan provenance・権利・scale・hashを満たすものだけを
   別レイヤーへ採用する。

この順序は実コーパス、blind result、解読主張の公開を先行させるためでは
ない。source repository自体は公開済みである。権利不明データ、同一遺物
漏洩、循環評価を遮断し、将来の仮説を同じ試験台で比較できる状態を作る
ためである。
