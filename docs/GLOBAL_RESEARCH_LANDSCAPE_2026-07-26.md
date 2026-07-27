# インダス文字研究・世界調査報告

基準日: 2026-07-26
状態: 内部調査版。解読・翻訳の主張ではない。

2025–2026年の公開リポジトリ、モデル、合成データ、Unicode・フォント・3D資源は、
[2026-07-27世界オープンソース監査](GLOBAL_OPEN_SOURCE_AUDIT_2026-07-27.md)
でcommit・DOI単位に追補した。

## 結論

世界の公開情報、主要コーパス、研究機関、一次論文、2025–2026年の新説、
オープンソース、画像権利、賞金の制度化状況を横断調査した。現時点の結論は次のとおり。

1. 専門家に受容されたインダス文字の解読は、まだ存在しない。
2. 符号列に強い位置・順序制約があること、主方向が右から左らしいことはかなり確かである。
3. それが話し言葉を完全に符号化した文字か、言語を特定できるか、各符号の音・意味は何かは
   未解決である。
4. 世界にも、一次画像、転写、考古学的文脈、異体字、重複関係、権利を統合した
   オープンな標準コーパスはない。
5. 日本はインダス文明考古学で「ゼロからの後発」ではない。一方、継続的な計算碑文学拠点、
   国際データ協定、再現可能な盲検ベンチマークでは遅れている。
6. したがって最初に行うべき仕事は、新しい訳文を作ることではなく、世界の研究を監査し、
   データと主張を同じ試験台に載せることである。

後発でも勝機は残っている。世界の弱点も、日本の弱点と同じ「統合・権利・検証」にあるためである。

## 調査の判定階層

情報量の多さを、証拠の強さと混同しない。今後の知識台帳では次の階層を使う。

| 層 | 内容 | 使い方 |
|---|---|---|
| A | 発掘記録、所蔵館記録、一次画像、公式コーパス | 観察事実の根拠 |
| B | 査読済みの構造・統計・画像処理研究 | 再現後に方法上の根拠 |
| C | 査読済みの言語・意味・機能仮説 | 競合仮説として比較 |
| D | プレプリント、会議稿、公開コード、未査読データ | 監査対象。結論扱いしない |
| E | 自主出版、ブログ、SNS、出典不明データ | 主張追跡と反証に限る |

「ドラヴィダ語説」「インド・アーリア語説」「非言語体系説」を、支持する文化的・政治的立場で
格付けしない。固定規則、全資料への適用、例外率、未見資料への予測、独立再現で判定する。

## 現在までに分かっていること

| 論点 | 現在の証拠 |
|---|---|
| 時代 | 主資料は成熟期ハラッパー文明、概ね前2600–1900年 |
| 媒体 | 印章・印影が中心。小板、土器、銅製品などもある |
| 長さ | 多くは約4–5符号。長文も確実な二言語碑文も未発見 |
| 方向 | 多数は右→左。左→右、牛耕式、印章と印影の反転に注意 |
| 符号数 | 分類法により約400から700超。異体字・合字・破損の扱いが未統一 |
| 構造 | 語頭・語末に相当し得る位置クラス、頻出連鎖、方向非対称性がある |
| 数 | 短い縦線群などは数的記号である可能性が高いが、単位と対象は未確定 |
| 言語 | 不明。原ドラヴィダ語説が最も精緻だが証明されていない |
| 音価・意味 | 合意された対応はない |
| 文字か | 多数説は文字体系。言語を符号化しない記号体系説も未決着 |

Archaeological Survey of Indiaも2025年の公式会議文書で、二言語資料の欠如、短文、
文字体系と言語の不確実性を主要障害として列挙している。

- [ASI: Decipherment of Indus Script — Current Status and Way Forward](https://asi.nic.in/admin/whatsnew/download/771)
- [Parpola: Tasks, Methods and Results in the Study of the Indus Script](https://www.cambridge.org/core/journals/journal-of-the-royal-asiatic-society/article/abs/tasks-methods-and-results-in-the-study-of-the-indus-script/E77A33DECB89FBB5327234211D83AE70)

## 世界の中核コーパスとデータ

### CISI

*Corpus of Indus Seals and Inscriptions* は、UNESCO支援で作られた事実上の写真標準である。
印章、印影、転写を高品質に集成する一方、紙の図録が中心で、構造化APIや包括的な
オープンライセンスはない。写真・図版・転写の再配布やAI利用は、権利者・所蔵機関との合意が必要。

- [Finnish Academy of Science and Letters: CISI 3.2](https://acadsci.fi/en/publications/the-corpus-of-indus-seals-and-inscriptions-3-2-humaniora-383-has-been-published/)
- [University of Helsinki: CISI project](https://researchportal.helsinki.fi/en/projects/corpus-of-indus-seals-and-inscriptions/)

### Mahadevan 1977 / RMRL IndusScript

Iravatham Mahadevanの1977年コンコーダンスは、現代研究の主要な参照体系である。
RMRL Indus Research Centreはこれを `IndusScript.in` に移植し、2025年設置の
Iravatham Mahadevan Chairで拡張コンコーダンスを計画している。

閲覧可能であることは、データを自由に複製・再配布できることを意味しない。
公式サイトはAPI、バルク出力、機械可読データのライセンスを掲示せず、
サイト全体は `All rights reserved` としている。

- [RMRL Indus Research Centre](https://www.rmrl.in/en/irc)
- [IndusScript](https://indusscript.in/)
- [Mahadevan research papers](https://rmrl.in/en/dl/research-papers/mahadevan)

### ICIT

Bryan K. WellsとAndreas Fulsの *Interactive Corpus of Indus Texts* は、符号列、位置、
統計、地理分布を扱える重要な関係データベースである。公式ページは管理者へのアクセス申請を
求めており、公開ダウンロードや再配布ライセンスは確認できない。

版や数え方により、遺物数、テキスト数、符号数の公表値が異なる。数字を引用するときは
必ず版・日付・除外規則を添える必要がある。

- [ICIT official page](https://www.epigraphica.de/indus/menueindus.htm)
- [ICIT documentation](https://www.epigraphica.de/indus/help_onlinedatabase.pdf)

### mayig

[mayig/indus-valley-script-corpus](https://github.com/mayig/indus-valley-script-corpus) は、
現在もっとも処理しやすい公開JSONの一つである。監査した
`ad2f1e218a34b8c33c57de0d6cb8d99272765bbb` には179件、1,003トークンがある。

ただし全件がモヘンジョダロの一角獣印章であり、画像、年代、層位、出土地、材質、
複製・同型関係を欠く。MITライセンスはリポジトリのコードと内容に付されているが、
CISI由来の第三者資料の権利まで自動的に解決しない。全インダス資料を代表する学習・評価コーパス
としては使えない。

### 権利を確認できた少数画像

Metropolitan Museum of ArtとCleveland Museum of Artには、CC0と明示された関連遺物画像が
少数ある。これらは画像取得、ハッシュ、注釈、IIIF/API接続の試験には使えるが、
解読学習には小さすぎる。

- [The Met Open Access](https://www.metmuseum.org/hubs/open-access)
- [The Met Collection API](https://metmuseum.github.io/)
- [Cleveland Museum Open Access API](https://www.clevelandart.org/open-access-api)

### 閲覧可能だが自由利用できない資源

- [Harappa.com](https://www.harappa.com/content/about-us-credits) は大量の画像と考古学解説を
  持つが、現行規約は素材のAI/ML開発・学習への組込みを禁止し、利用には個別許可を求める。
- [British Museum](https://www.britishmuseum.org/terms-use/copyright-and-permissions)、
  Penn Museum、Smithsonianは個別記録ごとに権利条件が異なる。
- [Museums of India](https://www.museumsofindia.gov.in/) と
  [NMMA](https://nmma.nic.in/) は重要な公式記録を持つが、包括的なAPI・再利用・AI学習条件を
  確認できない。

最大の世界的データ問題は「データが少ない」だけではない。CISI、Mahadevan、Wells/ICIT間の
遺物ID・符号ID対応、版、重複、印章/印影、異体字、権利が一つにつながっていないことである。

## オープンソースの現状

公開コードはあるが、コードのライセンスと入力画像・転写の権利を分けて監査する必要がある。

| 資源 | 利用価値 | 主な制約 |
|---|---|---|
| [mayig corpus](https://github.com/mayig/indus-valley-script-corpus) | JSON変換、転写パイプライン | 小規模・単一遺跡/意匠・画像なし・上流権利 |
| [indus-script-ocr](https://github.com/tpsatish95/indus-script-ocr) | 2017年画像認識研究のコード | 元画像非公開、主に壺形符号の二値分類 |
| [ASDA code](https://github.com/DM-BiCLab/Deep-Learning-in-Archiving-Indus-Script-and-Motif-Information) | 符号・モチーフ抽出 | 完全データは申請制、元画像権利は別 |
| [AI-EPIGRAPHY](https://github.com/atulsharma0071/indiahci2025) | 頻度、位置、遷移、仮説探索 | 研究支援UIであり翻訳器ではない |
| [ivc2tyc](https://github.com/oohalakkadi/ivc2tyc/tree/v1.0.0) | 比較画像埋め込みの再現 | 一次銘文コーパスではなく、第三者データ権利が残る |
| `yajnadevam/lipi` | 仮説探索の参考 | ライセンスなし、観察と独自解釈が混在 |
| 出典不明の画像データセット群 | なし | 無ライセンス、書籍・Harappa.com由来、品質不明 |

Private Use Areaへ独自に割り当てた「Indus font」も複数ある。見た目が同じでも符号IDの互換性はなく、
フォントがMIT/GPLでも字形の出典権利が解決するとは限らない。

## 世界の主要拠点

### インド

- [RMRL Indus Research Centre](https://www.rmrl.in/en/irc): Mahadevan系コーパス、
  IndusScript、Tamil Nadu graffiti portal、新コンコーダンス。
- [IMSc Computational Epigraphy Lab](https://www.imsc.res.in/~sitabhra/meetings/bitsscripts25/):
  統計解析、分節、計算碑文学ワークショップ。
- [IIT Gandhinagar Archaeological Sciences Centre](https://asc.iitgn.ac.in/people.php):
  ハラッパー考古学、古代技術、3D/GIS。
- [Florida Tech / Indian Statistical Institute ASDA](https://digitalcommons.isical.ac.in/journal-articles/5303/):
  符号・動物モチーフの画像抽出とアーカイブ。
- [Mahindra University](https://www.mahindrauniversity.edu.in/media-releases/mahindra-university-hosts-symposium-to-mark-100-years-of-discovery-of-indus-valley-civilisation-2/):
  2025年に考古学・言語学・認知科学・AIの学際チームを発表。
- Archaeological Survey of Indiaと文化省は2025年に解読会議を開催した。ただし会議での発表は、
  各解読説の承認を意味しない。

2026年2月12日のRajya Sabha公式答弁は、中央政府のインダス解読事業を問われ、
2025年Gyan Bharatam会議のテーマを挙げるにとどまった。公開答弁からは、専用の国家的な
継続プロジェクトは確認できない。

- [Rajya Sabha Unstarred Question 1462](https://sansad.in/getFile/annex/270/AU1462_nP8UIP.pdf?source=pqars)

### パキスタン

主要遺跡、原物、原写真、発掘文脈の多くを所管するため、パキスタン抜きの国際コーパスは成立しない。

- [Federal Department of Archaeology and Museums](https://doam.gov.pk/public/)
- [Sindh Directorate General of Antiquities and Archaeology](https://antiquities.sindhculture.gov.pk/)
- [Punjab Directorate General of Archaeology: Harappa](https://archaeology.punjab.gov.pk/arch-sites-harappa)
- HARPはHarappaで文字資料を発掘文脈と一緒に研究してきた。

2025年4月のPakistan Business Council会合では、Punjab州政府部門のDirector Generalが
Harappaの「Indus Valley decipherment center」計画を説明した。2026年の博物館刷新情報にも
同様の計画が現れるが、公開サイト上で研究組織、データ、採用、成果まで確認できる
稼働中センターとはまだ判定しない。

- [PBC proceedings, pp.18](https://www.pbc.org.pk/wp-content/uploads/Proceedings-from-PBCs-Event-Apr14-2025-Reimagining-Tourism-as-a-Pathway-to-Pakistans-Economic-Growth.pdf)

### フィンランド・ドイツ

- University of Helsinki / Finnish Academy系はCISIとAsko Parpolaの長期研究を担う。
- Wells/FulsのICITはドイツのEpigraphica上で継続している。

### 英国・米国

- [Cambridge MAHSA](https://www.arch.cam.ac.uk/research/projects/current-projects/mapping-archaeological-heritage-south-asia)
  は2029年まで、南アジア遺跡をリモートセンシング、歴史地図、機械学習で記録し、
  Open Access Arches DBを構築する。
- TIFR、IMSc、University of Washingtonの共同研究は統計的構造研究の中核を作った。
- University of Wisconsin–Madison / HARPは印章生産、筆記者差、出土文脈を研究してきた。
- University of Nebraska系の研究は異体字・鏡像候補を計算的に扱う。

### 日本

日本は完全な後発ではない。

- 総合地球環境学研究所の長田俊樹「インダス・プロジェクト」は、KanmerとFarmanaの発掘、
  Language Atlas of South Asia、環境・物質文化・言語・DNAを統合した大規模国際研究を行った。
  Kanmerではインダス文字を持つ封泥状ペンダントも発見した。
- 上杉彰紀を代表とする2022–2027年KAKEN研究は、工芸品、生産、流通、社会の考古学的文脈を
  継続研究している。
- 小茄子川歩らには印章生産・社会構造の専門知がある。

- [RIHN Indus Project annual report](https://www.chikyu.ac.jp/rihn/activities/cr/rihnAnnualReport/15en.html)
- [RIHN completed project](https://www.chikyu.ac.jp/rihn/activities/project/detail/49/)
- [Kanazawa University current grant list](https://isac.w3.kanazawa-u.ac.jp/en/research/grant-in-aid.html)

今回確認できた公開情報では、日本に2026年現在、インダス文字専用の恒常的な計算研究コンソーシアム、
世界標準の公開コーパス、所蔵機関が保持する盲検テストは見つからなかった。

正確な評価は次である。

> 日本はインダス文明の考古学研究には参加してきたが、考古学、画像、計算、比較言語学、権利、
> 盲検評価を継続的に結ぶ研究基盤では遅れている。

## 主要仮説と現在の評価

### 原ドラヴィダ語説

Asko Parpola、Iravatham Mahadevanらが最も精緻に展開した。代表例は魚形符号を
原ドラヴィダ語の *mīn*「魚／星」の同音関係で読む仮説である。

位置、合字、再建語、考古学・宗教史を結びつける長所がある。一方、絵の同定、同音語、
後代神話の選択自由度が大きく、固定した音価で全コーパスを一意に翻訳したり、
未見資料を予測したりできていない。MahadevanとParpolaの個別解釈も一致しない。

- [Parpola 2010: A Dravidian Solution](https://tuhat.helsinki.fi/ws/portalfiles/portal/127256525/Parpola_A_2010._A_Dravidian_solution_to_the_Indus_script_problem.pdf)
- [Mahadevan interview](https://www.harappa.com/content/iravatham-mahadevan-complete-interview)

### インド・アーリア語／サンスクリット説

S. R. Raoなど複数の提案があるが、符号統合、年代、方向、音韻規則、全資料への適用で
合意を得ていない。Jha–Rajaram説は、画像、読字方向、符号の加工に重大な問題が指摘された。

言語候補だけで疑似科学と判定してはならない。どの言語説も同じ事前登録・盲検試験にかける。

- [Mahadevan 2002: Aryan or Dravidian or Neither?](https://hasp.ub.uni-heidelberg.de/journals/ejvs/article/download/833/920/0)

### 非言語的記号体系説

Farmer、Sproat、Witzelは、短さ、長文・筆記具の欠如、低頻度符号、反復の少なさなどから、
氏族、宗教、政治、行政を示す非言語的記号体系を提案した。

反論側は、印章の固有名詞・称号なら短くてよいこと、表語体系では低頻度符号があり得ること、
強い位置規則を指摘する。ただし、規則性だけで人間言語を証明することもできない。

- [Farmer, Sproat, Witzel 2004](https://hasp.ub.uni-heidelberg.de/journals/ejvs/issue/view/87)
- [Parpola 2008 response](https://tuhat.helsinki.fi/ws/portalfiles/portal/127257407/Parpola_A_2008._Is_the_Indus_script_not_a_writing_system_Airavati_111_131.pdf)

### 行政・交易・徴税などの機能仮説

出土場所、印章・封泥、度量衡、工房、門、倉庫との関係から、税、交易、工芸管理、
商品・アクセス管理を推定する研究がある。これは有力な意味領域仮説になり得るが、
個々の符号の音価や翻訳を確立したものではない。

- [Mukhopadhyay 2023](https://www.nature.com/articles/s41599-023-02320-7)

## 計算研究の到達点

| 研究 | 得られたもの | 得られていないもの |
|---|---|---|
| Rao et al. 2009 | 条件付きエントロピー、方向・順序制約 | 言語、音価、意味 |
| PNAS Markov model 2009 | 語頭/語末候補、欠損符号予測 | 翻訳 |
| Yadav et al. 2010 | Zipf型分布、n-gram、欠損復元 | 言語の確定 |
| Network analysis 2011 | 階層・部分列・結合構造 | 人間言語の証明 |
| Deep learning 2017 | 画像から壺形符号を検出する初期実験 | 全符号OCR、読解 |
| Allograph study 2021 | 異体字候補の圧縮 | 候補同一性の確定 |
| ASDA 2025 | 符号・動物モチーフの自動アーカイブ | 意味解読 |
| Tiwari 2026 | 方向非対称、位置制約、視覚クラスタ | 言語判定、翻訳 |

主要一次資料:

- [Rao et al., PNAS 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC2721819/)
- [Yadav et al., PLOS ONE 2010](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0009506)
- [Network analysis](https://aclanthology.org/W09-3202/)
- [Deep Learning the Indus Script](https://arxiv.org/abs/1702.00523)
- [Allographs, Humanities and Social Sciences Communications 2021](https://www.nature.com/articles/s41599-021-00713-0)
- [ASDA / JCAA 2025](https://digitalcommons.isical.ac.in/journal-articles/5303/)
- [Tiwari 2026, ACL Anthology](https://aclanthology.org/2026.nlp4dh-1.28.pdf)

エントロピー、Zipf則、n-gram精度、低いニューラル損失、視覚類似性は、
構造を示しても翻訳を示さない。

## 2025–2026年の新説監査

### Tiwari 2026

ACL NLP4DH workshop論文は6,579銘文、視覚クラスタ、エントロピー、HMM、BiLSTMを報告する。
著者自身も「言語を符号化するかは決定できない」と明記する。

再現前に解決すべき点がある。

- 6,579という数が主要な公刊コーパス数より大きく、来歴と重複除去が十分に記載されていない。
- 分割は遺物種別で層化した80/20で、同一印章、印影、複製、同一文字列のリーク遮断が不明。
- 論文はコード・データを公開予定とするが、基準日には具体的なリポジトリを確認できない。
- 表4では実資料のperplexity 2.60に対し、改変列が1.10、1.39、2.42とむしろ低い。
  本文の「改変列に低い確率」という説明との整合を追試する必要がある。

### Nair 2026

1,916件の重複除去列を、人工的な紋章・行政体系と実在の非言語体系に比較し、
インダスはどちらにもきれいに一致しない中間的位置と報告する。これは
「言語と確定」でも「非言語と確定」でもない。arXivプレプリントであり、
ICIT/Yajnadevam派生データの来歴、転写、符号体系依存を監査する必要がある。

- [How Non-Linguistic Is the Indus Sign System?](https://arxiv.org/abs/2604.17828)

### Ross 2026 — treewidth主張の独立再計算

2026年7月21日に更新されたZenodoプレプリント
[Reading the Indus Valley Script](https://zenodo.org/records/19362548) は、
mayigの178印章・1,003トークンから隣接共起グラフのtreewidthを26とし、
「非言語ラベル系の閾値2」を13倍上回るため言語である、と主張する。

公開データと記載手順を使い、次の条件で独立再計算した。

- mayig revision: `ad2f1e218a34b8c33c57de0d6cb8d99272765bbb`
- imported corpus SHA-256:
  `50ac90a3771f7ddabfb38344b49cf952e5371cd766792bc29b20ee0350275815`
- 無向隣接グラフ、自己ループ除外
- 決定論的なminimum-degree eliminationによるtreewidth上限
- 遺物単位にupstream grapheme indexで平坦化、長さ1も保持
- 乱数seed: `20260726`
- 100回の帰無反復

観測treewidth 26は再現した。しかし帰無モデルは次の結果になった。

| 帰無モデル | 最小 | 平均 | 中央値 | 最大 | 26以上の反復 |
|---|---:|---:|---:|---:|---:|
| 全トークン頻度と各列長を保存して再配置 | 25 | 28.73 | 29 | 32 | 99% |
| 各遺物内の符号構成を保存し、順序だけシャッフル | 23 | 27.23 | 27 | 30 | 93% |
| 実測頻度から独立同分布で生成 | 26 | 30.32 | 30 | 34 | 100% |

高いtreewidthが言語性の証拠だという検定なら、見るべき裾は帰無値が観測値以上になる割合である。
それが93–100%なので、少なくともこのコーパスとグラフ定義ではtreewidth 26だけで言語性を
判別できず、「非言語過程では模倣できない」という主張は支持されない。ただし、これらの単純な
帰無モデルから「非言語体系である」と逆向きに結論することもできない。

公開コーパスの件数にも注意が必要である。

- 全データ: 179列、1,003トークン、182符号。長さ1の `M-137A/P379` を含む。
- 長さ1を除外: 178列、1,002トークン、181グラフ頂点、1連結成分。
- 全符号を頂点に加える: 182頂点だが、孤立した `P379` により2連結成分。

プレプリントの「178列、1,003トークン、182頂点、1連結成分」は、公開データから同じ除外規則で
同時には成立しない。これは即座に全内容を否定するものではないが、言語判定と152符号の意味付与を
受け入れる前に、コード、除外規則、帰無分布、外部コーパス試験が必要である。

実装、境界別の全件数、推定量の注意点、再現コマンドは
[Ross 2026 treewidth reproduction audit](ROSS_2026_TREEWIDTH_AUDIT.md) に固定した。

### 視覚類似研究

2026年にはインダス符号とTibetan–Yi Corridor系の視覚類似を比較するコード・データが公開され、
PCI Archaeologyの推薦を受けた。再現性向上は評価できる一方、形の近さは、歴史的接触、
系統関係、同じ言語、同じ音価をそれだけでは示さない。

- [ivc2tyc code/data archive](https://zenodo.org/records/21158710)

### 自主公開の「完全解読」

Zenodo、ResearchGate、GitHub、Hugging Faceには、2025–2026年だけでも
Proto-Dravidian、Old Indo-Aryan、行政コード、星座、社会階層などを読む多数の主張がある。
これらを無視はしないが、査読、一次画像、固定した規則、全コーパス例外率、盲検予測、
独立再現を満たすまでは、D/E層の仮説カードとして扱う。

合成データが「本物らしい」こと、LLMが一貫した訳文を出すこと、辞書が手元の符号を100%覆うことは、
解読成功率ではない。

## 100万ドル賞金

発表者は「リン首相」ではなく、インド・Tamil Nadu州首相のM. K. Stalinである。
インド首相ではない。2025年1月5日の国際会議で、考古学者が有効な解決と認める突破口に
100万米ドルを授与すると発表し、州政府の後日の公式回顧資料にも明記された。

- [Tamil Nadu Government official retrospective](https://tamildigitallibrary.in/assets/docs/uploads/catalogue_article_file/PER/upload/2025/09/TVA_TVA_PER_040818/upload_primary_20250919120756159_21250919120047.pdf)
- [RMRL Annual Report 2024–25](https://rmrl.in/annual-report/2024-2025.pdf)

しかし基準日までに、州考古局、Tamil Nadu Awards、州政府/DIPR、予算、Government Order、
Gazette、RMRLを英語・Tamil語で追跡しても、次を公開確認できなかった。

- 募集要項、応募フォーム、提出先、締切
- 応募資格と提出形式
- 審査員、利益相反規程、評価基準
- 賞金予算を執行するGovernment Orderと予算科目
- 応募件数、審査状況、受賞者

正確な判定は次である。

> 100万ドルの政治的・政策的発表は本当だが、2026-07-27現在、
> 公開情報から応募可能な賞金制度になったとは確認できない。

2026年7月27日の公式資料再点検、予算項目、検索範囲、判断限界は
[賞金ステータス監査](TAMIL_NADU_PRIZE_STATUS_2026-07-27.md)に分離した。

同時発表された2 crore rupeesのIravatham Mahadevan Chairは、RMRL公式ページで
2025年設置とされ、研究計画が公開されている。この制度化の非対称性も、賞金を
「すぐ請求できるコンテスト」と扱わない理由である。

## 日本が追いつくための90日調査計画

### 0–14日: 世界知識台帳

- コーパス、発掘報告、所蔵館、論文、コード、解読説を一意IDで登録する。
- A–Eの証拠層、版、URL/DOI、取得日、権利、上流資料、主張、反証条件を記録する。
- Mahadevan、CISI、Wells/ICITの遺物ID・符号ID横断表の仕様を決める。
- 英語、日本語、Tamil語、Hindi語、Urdu語、German語、Finnish語の検索語を固定し、
  定期差分検索にする。

### 15–30日: 権利・所蔵・協力地図

- RMRL、ICIT、CISI、ASI、India/Pakistanの所蔵機関に求めるデータ項目と権利条件を整理する。
- 「メタデータ」「転写」「字形」「写真」「切り抜き」「埋め込み」「商用利用」を分離する。
- CC0画像だけで取得、ハッシュ、注釈、来歴の小規模パイプラインを検証する。
- 外部連絡や契約提案は、内容と名義を確認してから行う。

### 31–60日: 世界主要結果の再現

- Rao/PNAS、Yadav/PLOS、network analysis、allograph、Tiwari、Nairを同じ監査済み入力で再現する。
- 遺物・鋳型・同一列・画像ハッシュ単位でリークを遮断する。
- 言語、行政コード、紋章、数体系、シャッフルを同じ条件で比較する。
- 「再現」「再現不能」「データ不足」「権利で検証不能」を区別して公開前の内部報告にする。

### 61–90日: 仮説競争の準備

- Proto-Dravidian、Indo-Aryan、Munda/未知言語、非言語モデルの仮説カードを事前登録する。
- 固定音価、固定語義、許容異体、例外、年代制約、反証予測を明記する。
- 未使用の遺跡・遺物種・時期を、外部機関が保持する盲検テストとして設計する。
- 二言語碑文がなくても検証できる、数字、欠損符号、印章/印影、同型資料、出土文脈の
  予測課題を先に作る。

## 解読成立の最低基準

次を満たさないものは「解読候補」に上げない。

1. 出土地・年代・所蔵・画像が追跡できる。
2. 印章/印影、表裏、破片、複製、同型品を区別する。
3. 読字方向と分節を都合に応じて変えない。
4. 符号の音・意味を例ごとに変えず、変更規則を事前固定する。
5. 全コーパスの適用率と例外率を示す。
6. 後代辞書の似た語を拾うだけでなく、前3千年紀に適合する規則的音韻対応を示す。
7. 複数言語説と非言語モデルを同じデータ・指標で比較する。
8. 遺物、遺跡、時期、同型群を完全分離した未使用テストを使う。
9. シャッフル、頻度保存、単純行政コードなど強い帰無モデルに勝つ。
10. 新出・非公開資料を事前予測し、独立研究者が再現する。

最強の外部アンカーは、二言語碑文、長文、既知固有名詞、音声補語、既知の度量衡との一貫した対応である。

## 当面の公開方針

この調査は、解読前の公開を急ぐ理由にはしない。

- 解読・翻訳の主張を外部発表しない。
- 権利未確認の画像・転写を公開リポジトリや学習に入れない。
- 新説は内部で先に帰無試験、盲検、独立再現へ回す。
- 公開するとしても、将来、権利確認済みの出典台帳、再現コード、否定結果、
  検証手順から段階的に行う。

世界調査は一度で終了する文献レビューではない。版、論文、発掘、制度、権利の更新を追う
継続的な情報戦として運用する。
