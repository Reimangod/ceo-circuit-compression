# 論文用保存構成の根拠

JCTCのResearch Data Policy Level 2は投稿時のData Availability Statementを求め,
結果を支えるデータの公開と引用を勧めている. JCTC/JCIMの2026年の共同編集記事は,
主要結果の再現に必要なコード, 入出力, 物理条件, 数値データ, 実行環境,
ライセンスを共有する方針を示した.

- https://researcher-resources.acs.org/publish/author_guidelines?coden=jctcce
- https://doi.org/10.1021/acs.jctc.6c00733
- https://doi.org/10.1371/journal.pcbi.1005510

CEO公式Repositoryは固定実装, 実行例, 依存条件, Apache-2.0を提供しており,
今回も利用commitと原著の引用を保持した. VQEmultiの実行例・テスト構成を参考に,
小さな検証入口を設けた. ADAPT-VQEの保存データ例では反復ごとの数値と形式説明が
配布されており, 今回も最終表だけでなく回路, 中間記録, 費用台帳を残した.

- https://github.com/mafaldaramoa/ceo-adapt-vqe
- https://github.com/abelcarreras/VQEmulti
- https://zenodo.org/records/19051536

コード・軽量表はGitで管理し, 大きな原記録は固定版のRelease assetとした.
GitHubの単一Gitオブジェクト上限や生成物の保存指針に対応した.
全軌道41条件と最新Policy22条件の区分を設けることで,
旧版を最新手法の結果と誤認することを防いだ.

- https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits
- https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

GitHubのCITATION.cffによって引用方法を表示できる. 将来はZenodoで版を固定して
DOIを取得する構成とした. Private Repositoryの自動取り込みは利用できないため,
今回はGitHub内でPrivateの保存・取得を確認し, DOIの作成や公開は行わない.
ソフトウェアとデータの来歴・版を引用可能にすることは, ソフトウェア引用原則にも対応する.

- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files
- https://zenodo.org/help/versioning
- https://help.zenodo.org/docs/github/describe-software/
- https://doi.org/10.7717/peerj-cs.86

保存構成は論文の採択や性能優位性を保証する仕組みとは区別した.
新しい分子実験や大規模な承認制度を加える代わりに,
原資料の保全, 正しい区分, 図表の再生成, 費用と比較関係の照合に集中した.
