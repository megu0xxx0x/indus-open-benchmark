# 世界の博物館におけるインダス関連資料の権利監査

監査日: 2026-07-26
対象: MetおよびCleveland Museum of Art以外の追加候補
根拠: 所蔵館・運営主体が公開する一次情報のみ
状態: 候補調査。画像取得、スクレイピング、外部連絡、利用許諾の申請は未実施

## 結論

今回確認した追加候補には、インダス関連の実物資料と画像を、許諾なしに
一括自動取得し、長期保存し、オープン・ベンチマークで再配布できると確認済みの
所蔵館はなかった。

直ちに利用できる追加レイヤーは次の二つに限られる。

- Penn MuseumがCC BY 4.0で公開する、画像を含まない一括メタデータ
- Smithsonianの各レコードで明示されたCC0メタデータ

SmithsonianはAPI、JSONL、IIIFを備えるが、今回確認したHarappan資料の画像は
`Usage Conditions Apply`であり、CC0ではない。したがって、当該資料は
メタデータだけを候補にできる。APIまたはIIIFの存在自体を、保存や再配布の許可と
解釈してはならない。

MetとClevelandのCC0候補は本監査の対象外であり、公開source registryと
取得ゲートの判断は別途管理する。

## 判定語

| 判定 | この監査での意味 |
|---|---|
| メタデータのみ可 | 公式根拠によりメタデータの長期保存・再配布を認められるが、画像には同じ許可がない |
| 要許諾 | 自動取得、長期保存、計算利用または再配布のいずれかについて明示的な許可がない、または禁止・申請条件がある |
| 探索専用 | APIを候補発見に利用できるが、保存期限またはホットリンク条件のため、持続的なベンチマーク台帳・画像コーパスには取り込めない |
| 監視候補 | オープンアクセス基盤は確認できるが、対象となるインダス資料を今回確認できていない |

「ウェブ上で閲覧可能」「ダウンロードボタンがある」「APIがある」
「IIIF manifestが返る」は、いずれも単独では再配布許可を意味しない。

## 厳格判定一覧

| 優先順位 | 機関 | 確認資料 | 機械可読性 | 現時点の判定 | 主な障害 |
|---:|---|---|---|---|---|
| 1 | National Museum, New Delhi / Museums of India | 7・8文字の印章、封泥等 | 公式HTML、高解像度ズーム。公開API・IIIFは未確認 | 要許諾 | 個別ライセンスと自動取得許可が未確認 |
| 2 | British Museum | Mohenjo-daroおよびUr出土のインダス文字印章 | 公式HTML。現行の公開JSON API・IIIFは未確認 | 要許諾 | TDMは要連絡。画像は主にCC BY-NC-SA |
| 3 | Penn Museum | Harappanの石膏製印章押型 | 一括メタデータをダウンロード可能 | メタデータのみ可 | CC BY 4.0の一括データに画像は含まれない |
| 4 | Smithsonian | Mohenjo-daroのHarappan印章キャスト等 | Open Access API、JSONL、IIIF | メタデータのみ可 | 当該画像は`Usage Conditions Apply` |
| 5 | Brooklyn Museum | Chanhu-Daro由来の文脈資料 | 個別HTML。旧APIは現行仕様を確認できず | 要許諾 | 現行規約が自動アクセス・保存を原則禁止 |
| 6 | LACMA | Indus Valley Civilizationの儀礼用容器 | 個別HTML。公開API・IIIFは未確認 | 要許諾 | 当該画像にPublic Domain表示がない |
| 7 | Harvard Art Museums | 対象資料を未確認 | REST API、IIIF | 探索専用 | API内容は2週間超保存不可。画像はホットリンク・非商用 |
| 8 | V&A | 対象資料を未確認 | REST API、IIIF | 探索専用 | API内容は4週間超保存不可。画像のローカル複製不可 |
| 9 | Art Institute of Chicago | 対象資料を未確認 | REST API、IIIF | 監視候補 | 個別の対象資料を確認していない |
| 10 | Yale University Art Gallery | 対象資料を未確認 | 個別権利表示、IIIF対応 | 監視候補 | 個別の対象資料を確認していない |
| 11 | Walters Art Museum | 対象資料を未確認 | 旧API終了、静的データへ移行中 | 監視候補 | 対象資料未確認、API v2未提供 |

## 1. National Museum, New Delhi / Museums of India

### 確認できた公式資料

- [パシュパティ印章 DK5175/143](https://museumsofindia.gov.in/repository/record/nat_del-DK-5175-143-4814)
- [一角獣と8個の絵文字を持つ印章 180/9](https://museumsofindia.gov.in/repository/record/nat_del-180-9-8919)
- [3個の絵文字を持つ封泥 201/33](https://www.museumsofindia.gov.in/repository/record/nat_del-201-33-11909)
- [スワスティカ印章 hr-6163/170](https://www.museumsofindia.gov.in/repository/record/nat_del-hr-6163-170-38126)
- [National Museum所蔵品一覧](https://www.museumsofindia.gov.in/repository/museum/nat_del)
- [Museums of Indiaの概要](https://museumsofindia.gov.in/repository/page/about)

これらは今回の候補中で最も直接的な文字資料であり、科学的優先順位は最上位である。
一方、公開API、IIIF、機械可読な権利フィールド、画像またはメタデータに対する
オープンライセンスを確認できなかった。サイトのフッターは権利留保を表示する。
また、文化省が公開するNMMA関連資料でも、データと画像がNMMA/ASIの財産であり、
第三者利用に制約があることが示されている。

- [Ministry of CultureのNMMA関連文書](https://www.indiaculture.gov.in/sites/default/files/circulars/merged_document_2.pdf)

判定は**要許諾**とする。許諾前に保存してよいのは、担当者が手動で確認した
資料ID、名称、公開レコードURLからなる候補台帳だけである。画像、ズーム用タイル、
ページHTMLのミラーを取得しない。

次の行動は、対象レコードを限定した上で、メタデータの機械可読な提供、ローカル計算、
画像保存、派生注釈、再配布の各条件を別々に問い合わせるための依頼案を準備すること
である。依頼送信は別途の明示的な承認を要する。

## 2. British Museum

### 確認できた公式資料

- [Mohenjo-daro出土、5文字の印章 1947,0416.1](https://www.britishmuseum.org/collection/object/A_1947-0416-1)
- [Ur出土、インダス文字印章 1929,1017.725](https://www.britishmuseum.org/collection/object/W_1929-1017-725)
- [1947,0416.1の画像とライセンス表示](https://www.britishmuseum.org/collection/image/1613597875)
- [1929,1017.725の画像とライセンス表示](https://www.britishmuseum.org/collection/image/1613619551)

公式画像ページは対象画像をCC BY-NC-SA 4.0として扱い、商用利用には別途の
ライセンスを求める。全体の著作権・許諾ページは、テキスト・データマイニングに
ついてBritish Museumへの連絡を求めている。

- [Copyright and permissions](https://www.britishmuseum.org/terms-use/copyright-and-permissions)
- [Images and photography](https://www.britishmuseum.org/terms-use/copyright-and-permissions/images-and-photography)

CC BY-NC-SAは、商用利用も可能なCC0主体の公開ベンチマークへ無条件に混在させられる
権利ではない。また、個別画像の非商用利用条件は、コレクション全体のクローリングや
TDM許可を置き換えない。判定は**要許諾**とする。

次の行動は、対象アクセッションを限定し、公式の機械可読エクスポート、
計算利用、保存期間、派生座標・転写の公開、画像再配布の範囲を確認することである。

## 3. Penn Museum

### 確認できた公式資料と一括データ

- [Harappan印章押型 89-13-408.2](https://collections.penn.museum/collections/object/490764)
- [対象資料の画像ページ](https://collections.penn.museum/collections/object_images.php?irn=490764)
- [一括コレクションデータ](https://collections.penn.museum/collections/objects/data.php)
- [利用規約](https://www.penn.museum/about/statements-and-policies/terms-and-conditions)
- [Rights and permissions](https://www.penn.museum/about-collections/rights-and-permissions)

一括メタデータはCC BY 4.0で提供され、画像を含まない。このレイヤーは出典表示を
維持すれば長期保存・再配布可能な候補である。ウェブ画像は研究、教育、個人的利用等の
非商用条件に限定され、高解像度画像および出版利用には別途の手続きがある。

判定は**メタデータのみ可**とする。公開コーパスに画像を含める場合は要許諾である。
確認資料は原印章ではなく石膏製の押型であるため、`original`と`cast/impression`を
同一視せず、物理形態を明示する必要がある。

次の行動は、公式一括メタデータの版・取得日・ハッシュを記録する取得計画を設計し、
Harappan候補だけをレビューすることである。画像取得はその計画に含めない。

## 4. Smithsonian

### オープンアクセス基盤

- [Smithsonian Open Access FAQ](https://www.si.edu/openaccess/faq)
- [公式OpenAccess JSONLリポジトリ](https://github.com/Smithsonian/OpenAccess)
- [公式APIヘルパーリポジトリ](https://github.com/Smithsonian/smithsonian-openaccess)
- [Mohenjo-daroのSeal Cast](https://www.si.edu/object/seal-cast%3Anmnhanthropology_8238874)
- [別のSeal Castレコード](https://collections.si.edu/search/detail/edanmdm%3Anmnhanthropology_8238875)
- [Pottery Figure Monkey Cast](https://www.si.edu/object/pottery-figure-monkey-cast%3Anmnhanthropology_8238882)

公式APIの代表的な入口は次のとおりである。

```text
GET https://api.si.edu/openaccess/api/v1.0/search?q=Harappan&api_key=...
GET https://api.si.edu/openaccess/api/v1.0/content/{record-id}?api_key=...
```

Smithsonianでは、CC0対象のメタデータとメディアを機械的に区別できる。ただし、
今回確認したSeal Castはページ上で`Metadata Usage: CC0`、画像は
`Usage Conditions Apply`とされる。IIIF manifestが提供されても、この画像状態は
変わらない。

メディアを自動採用できるのは、取得時の公式レスポンスにおいて、対象メディア自身が
次の条件を満たす場合だけである。

```text
content.descriptiveNonRepeating.online_media.media[].usage.access == "CC0"
```

欠落、`null`、`Usage Conditions Apply`、`Not determined`はすべて除外する。
現在確認済みのHarappan候補については**メタデータのみ可**である。キャストまたは
複製であるため、原資料と同等の考古学的観察として扱わない。

次の行動は、公式APIに対して権利フィールドをfail-closedで評価する
メタデータ探索計画を作ることである。実行時にも、メディアは個別にCC0が確認できる
まで取得しない。

## 5. Brooklyn Museum

### 確認できた公式資料

- [Chanhu-Daro出土の容器片 37.90](https://opencollection.brooklynmuseum.org/objects/3423)
- [Chanhu-Daro出土の小型車輪 37.94](https://opencollection.brooklynmuseum.org/objects/3425)
- [公式アーカイブ・ガイド](https://cdn2.brooklynmuseum.org/archives/Asian_final.pdf)
- [現行利用規約](https://www.brooklynmuseum.org/terms)
- [Image Services](https://www.brooklynmuseum.org/image-services)
- [旧Open Collection API入口](https://www.brooklynmuseum.org/opencollection/api)

個別ページにはCC BY表示を持つ資料がある一方、2024年改訂の現行規約は、
クローラー、スパイダーその他の自動手段によるアクセス、コピー、索引化、処理、
保存を、書面による明示許可なしには認めていない。個別ページとサイト全体の条件に
見かけ上の差がある場合、自動処理については厳しい方へ倒す。

判定は**要許諾**とする。Chanhu-Daro由来の文脈資料は候補台帳へ手動登録できるが、
文字を持つ資料であることは今回確認できていない。画像やHTMLを自動取得しない。

次の行動は、所蔵するChanhu-Daro資料中の文字資料の有無と、API・一括メタデータ・
画像の各利用条件を一つの書面回答で確認するための依頼案を準備することである。

## 6. LACMA

- [Ceremonial Vessel, AC1997.93.1](https://collections.lacma.org/object/64836)
- [LACMA Terms of Use](https://www.lacma.org/about/contact-us/terms-use)

LACMAでは、個別ページで明示的に`Public Domain High Resolution Image Available`
とされる画像だけが無制限利用の対象である。確認したCeremonial Vesselの画像は
Museum Associates/LACMAの著作権表示を持ち、当該Public Domain表示を確認できない。
公開API・IIIFも確認できなかった。

判定は**要許諾**とする。資料はインダス文明の文脈資料だが、インダス文字を持つとは
確認できていないため、科学的優先順位も文字資料より低い。

## 7. Harvard Art Museums

- [公式API仕様](https://github.com/harvardartmuseums/api-docs)
- [Object endpoint仕様](https://github.com/harvardartmuseums/api-docs/blob/master/sections/object.md)
- [公式コレクションの例](https://harvardartmuseums.org/collections/object/304204)

```text
GET https://api.harvardartmuseums.org/object/{id}?apikey=...
https://iiif.harvardartmuseums.org/manifests/object/{id}
```

APIには`copyright`、`images[].copyright`、`imagepermissionlevel`、
`baseimageurl`等がある。`imagepermissionlevel`は配信可能サイズのレベルであり、
再配布ライセンスではない。API条件は、内容を2週間を超えて保存しないこと、
画像をローカル複製せずホットリンクすること、非商用利用であることを求める。

今回、公式記録でインダス文字資料を確認できなかった。判定は**探索専用**である。
APIレスポンスや画像を持続的な台帳へ保存しない。

## 8. Victoria and Albert Museum

- [V&A APIガイド](https://developers.vam.ac.uk/guide/v2/welcome.html)
- [V&A API仕様](https://api.vam.ac.uk/docs)
- [V&A IIIFガイド](https://developers.vam.ac.uk/guide/v2/images/iiif.html)
- [V&Aウェブサイト利用規約](https://www.vam.ac.uk/info/va-websites-terms-conditions)

```text
GET https://api.vam.ac.uk/v2/objects/search?q=Indus
GET https://api.vam.ac.uk/v2/object/{systemNumber}
https://iiif.vam.ac.uk/collections/{systemNumber}/manifest.json
```

APIは非商用利用に限定され、API内容を4週間を超えて保存できない。表示する画像は
返されたURLをホットリンクし、ローカルコピーを作らない条件である。今回、公式記録で
インダス文字資料を確認できなかった。判定は**探索専用**である。

## 9. オープンアクセス監視候補

### Art Institute of Chicago

- [公式API仕様](https://api.artic.edu/docs/)
- [Public API案内](https://www.artic.edu/open-access/public-api)
- [Open Access Images](https://www.artic.edu/open-access/open-access-images)

対象資料が見つかった場合、次を同時に満たすレコードだけを画像候補にできる。

```text
is_public_domain == true
image_id != null
```

画像は公式IIIFから得られるが、今回インダス文字資料を確認できなかったため、
現時点では取得対象にしない。

### Yale University Art Gallery

- [Using Images](https://artgallery.yale.edu/using-collection/using-images)
- [Terms and Conditions](https://artgallery.yale.edu/terms-and-conditions)

パブリックドメイン作品の画像と個別の権利状態を確認でき、IIIFにも対応する。
ただし、今回インダス文字資料を確認できなかった。Yale University Art Galleryと
Yale Peabody Museumは別機関として扱い、権利条件を混同しない。

### Walters Art Museum

- [Rights & Reproductions](https://thewalters.org/about/policies/rights-reproductions/)
- [旧API案内](https://api.thewalters.org/)

パブリックドメイン作品の画像・メタデータはCC0対象となり得るが、API v1は終了し、
v2まで静的データ提供へ移行している。今回インダス文字資料を確認できなかったため、
監視候補に留める。

## 自動取得・公開の安全規則

1. APIまたはIIIFの存在を、画像保存・計算利用・再配布の許可とみなさない。
2. 採用判断はコレクション全体の説明だけでなく、取得時のアイテムまたは
   メディア単位の公式権利値に基づける。
3. 権利値が欠落、`null`、不明、判定不能、利用条件適用、申請制ならfail-closedで
   メディアを除外する。
4. Smithsonianは各`media[].usage.access`が厳密に`CC0`のメディアだけを候補にする。
5. Art Institute of Chicagoは`is_public_domain`が真で、`image_id`が存在する
   レコードだけを候補にする。
6. Harvardの`imagepermissionlevel`は表示制御であり、再配布許可として扱わない。
7. CC BY-NC-SA、研究・教育限定、個人利用限定の画像は、商用利用可能な公開データ本体へ
   混在させない。必要なら権利分離された非公開または制限付きレイヤーで管理する。
8. Brooklyn Museum、British Museum、Museums of India、LACMAは、書面確認前に
   HTML、画像、IIIFタイルをクローリングまたはミラーしない。
9. Harvardは14日、V&Aは28日を超えてAPI内容を保持しない。候補発見結果を永続化する
   場合も、規約で許された最小限の手動作成メタデータと公式URLに限定する。
10. 原資料、古代の印影、現代の石膏押型、キャスト、複製、模写を別の物理形態として
    記録し、画像類似を同一資料または独立証拠とみなさない。
11. 取得が認められた場合でも、公式レスポンス、権利根拠、取得時刻、受信バイト、
    SHA-256を保存し、公開前に権利状態を再確認する。
12. 保存期限のあるHarvard・V&Aでは、長期スナップショットの作成やレスポンスの
    リポジトリ登録を行わない。

## 実行優先順位

### 第1段階: 許可済みメタデータ

1. PennのCC BY 4.0一括メタデータについて、版、取得日時、ファイルハッシュ、
   出典表示を固定する取得計画を作る。
2. Smithsonian APIについて、CC0メタデータだけを取り込むfail-closedゲートを設計する。
3. いずれも画像取得を有効化しない。

### 第2段階: 高価値資料の許諾準備

1. Museums of Indiaの4件とBritish Museumの2件を最小対象として、
   `docs/PERMISSION_REQUESTS.md`に沿った問い合わせ案を準備する。
2. メタデータ、画像、ローカル計算、派生注釈、再配布、商用利用を別項目として尋ねる。
3. 自動送信せず、対象と文面を人間が承認するまで保留する。

### 第3段階: 所蔵確認

1. Brooklyn MuseumのChanhu-Daro資料に文字資料が含まれるかを公式回答で確認する。
2. Harvard、V&A、AIC、Yale、Waltersでは、規約上許される探索範囲で候補の有無だけを
   確認する。
3. 具体的な対象レコードとアイテム権利が同時に確認できるまで、画像取得機能を追加しない。

## 監査上の限界

- 本文は法的助言ではなく、公式公開条件に基づく保守的なデータ取扱判定である。
- 権利条件、API仕様、所蔵情報は変更され得る。実取得時と公開時に再確認する。
- 検索結果に現れない資料が所蔵されていないとは断定しない。
- 公式ページに明記されない許可を推定しない。
- 今回はページの確認だけを行い、画像、APIデータ、IIIF manifest、PDF本文の
  ローカル保存または再配布は行っていない。
