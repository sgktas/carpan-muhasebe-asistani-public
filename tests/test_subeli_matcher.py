from app.core.mapping_store import MappingStore
from app.core.subeli_matcher import SubeliMatcher
from app.models.records import ManimRecord, TahsilatRecord


def _manim(aciklama: str, tutar: float) -> ManimRecord:
    return ManimRecord(
        banka="Garanti", sube="123", islem_tarihi=None, aciklama=aciklama, tutar=tutar,
        dekont_durumu="Aktarıldı", karsi_hesap_adi="", karsi_hesap_kodu="",
        kaynak_dosya="test.xlsx", kaynak_satir=1,
    )


def test_direct_name_match_tek_musteri(tmp_path):
    tahsilat = [TahsilatRecord(musteri_kodu="C001", musteri_ismi="ORNEK MARKET", belge_tarihi=None, tutar=1000.0)]
    matcher = SubeliMatcher(tahsilat, [], MappingStore(tmp_path / "test_mapping_1.json"))
    result = matcher.match(_manim("FAST123-ORNEK MARKET ODEME", 1000.0))
    assert result is not None
    assert [row.musteri_kodu for row in result] == ["C001"]


def test_subset_sum_alakasiz_kaydi_disliyor(tmp_path):
    """Tamamen yapay bir çoklu tahsilat senaryosunun regresyon testi.

    Açıklamada "ORNEK" geçen 3 aday var ama sadece 2'sinin toplamı tutarı
    karşılıyor. Eskiden TÜM adayların toplamı isteniyordu ve bu durumda
    eşleşme başarısız oluyordu; artık doğru alt küme bulunmalı.
    """
    tahsilat = [
        TahsilatRecord(musteri_kodu="C001", musteri_ismi="ORNEK MARKET BIR", belge_tarihi=None, tutar=41781.25),
        TahsilatRecord(musteri_kodu="C002", musteri_ismi="ORNEK MARKET IKI", belge_tarihi=None, tutar=33616.00),
        TahsilatRecord(musteri_kodu="C003", musteri_ismi="ORNEK MARKET UC", belge_tarihi=None, tutar=12345.00),
    ]
    matcher = SubeliMatcher(tahsilat, [], MappingStore(tmp_path / "test_mapping_2.json"))
    result = matcher.match(_manim("FAST-ORNEK MARKET BIR VE ORNEK MARKET IKI TAH", 75397.25))
    assert result is not None
    codes = sorted(row.musteri_kodu for row in result)
    assert codes == ["C001", "C002"]


def test_zincir_tabela_adiyla_farkli_vknli_subeler_birlestirilir(tmp_path):
    """Yapay örnek: bir zincirin her şubesi ayrı VKN'li.

    Banka, VKN eşleşen tek şubenin tahsilatıyla tutmuyor ama ünvanda/tabelada
    ortak geçen nadir bir marka kelimesiyle (ZETA) diğer şubeler de havuza
    katılınca toplam birebir tutuyor.
    """
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("C-ZETA-1", "ORNEK PAZARLAMA GIDA TURZ.TIC.LTD.STI.ZETA MARKET 1", "1000000001", "SIMSEK-MARMARIS", ""),
        CustomerRecord("C-ZETA-2", "ORNEK PAZARLAMA GIDA TURZ.LTD.STI. ZETA MARKET 2", "1000000001", "SIMSEK-MARMARIS", ""),
        CustomerRecord("C-ZETA-3", "ALFA TOPTAN GIDA TURIZM VE TICARET LIMITED SIRKETI - ZETA MARKET 3", "1000000002", "SIMSEK-MARMARIS", ""),
        CustomerRecord("C-ZETA-4", "BETA GIDA TURIZM VE TICARET LTD.STI.-ZETA MARKET", "1000000003", "SIMSEK-MARMARIS", ""),
        # alakasiz, ZETA gecmeyen bir musteri - havuza girmemeli
        CustomerRecord("C-OTHER", "BASKA TEST MARKET ZINCIRI LTD STI", "1000000004", "SIMSEK-MARMARIS", ""),
    ]
    tahsilat = [
        TahsilatRecord("C-ZETA-1", "ZETA MARKET 1", None, 25546.25),
        TahsilatRecord("C-ZETA-1", "ZETA MARKET 1", None, 37149.50),
        TahsilatRecord("C-ZETA-2", "ZETA MARKET 2", None, 28124.75),
        TahsilatRecord("C-ZETA-3", "ZETA MARKET 3", None, 21583.00),
        TahsilatRecord("C-ZETA-4", "ZETA MARKET", None, 17858.50),
        TahsilatRecord("C-OTHER", "ALAKASIZ", None, 999999.00),
    ]
    matcher = SubeliMatcher(
        tahsilat, customers, MappingStore(tmp_path / "test_mapping_tabela_chain.json"),
        region_branch_aliases={"MUGLA": ("MARMARIS", "MUGLA")},
    )

    # Sadece C-ZETA-1'in VKN'si eslesecek aciklama; kendi tahsilati (62695.75)
    # banka tutarini (130262.0) karsilamiyor, zincirin tumu karsiliyor.
    hedef = 25546.25 + 37149.50 + 28124.75 + 21583.00 + 17858.50
    result = matcher.match(_manim("CEP ŞUBE-HVL- -ORNEK PAZARLAMA 1000000001 TR000...", hedef), "MUGLA")

    assert result is not None
    codes = sorted(row.musteri_kodu for row in result)
    assert codes == ["C-ZETA-1", "C-ZETA-1", "C-ZETA-2", "C-ZETA-3", "C-ZETA-4"]
    assert "C-OTHER" not in codes


def test_ayni_vknli_zincir_subeleri_bolgeler_arasinda_birlestirilir(tmp_path):
    """Aynı şirketin farklı bölge şubeleri tek banka tahsilatında toplanabilir.

    Denizli hareketi açıklamasında VKN bulunuyor; ancak tutar Aydın, Nazilli ve
    Denizli şubelerinin toplamı. Bölgesel ilk deneme yetersiz kalınca tüm aynı
    VKN kartları yalnız toplam tam tutuyorsa otomatik seçilmelidir.
    """
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("C-AYDIN", "ORNEK ZINCIR GIDA LTD STI", "1000000001", "SIMSEK-AYDIN", ".ORNEK AYDIN"),
        CustomerRecord("C-NAZILLI", "ORNEK ZINCIR GIDA LTD STI", "1000000001", "SIMSEK-NAZILLI", ".ORNEK NAZILLI"),
        CustomerRecord("C-DENIZLI", "ORNEK ZINCIR GIDA LTD STI", "1000000001", "SIMSEK-DENIZLI", ".ORNEK DENIZLI"),
    ]
    tahsilat = [
        TahsilatRecord("C-AYDIN", ".ORNEK AYDIN", None, 100.0),
        TahsilatRecord("C-NAZILLI", ".ORNEK NAZILLI", None, 200.0),
        TahsilatRecord("C-DENIZLI", ".ORNEK DENIZLI", None, 300.0),
    ]
    matcher = SubeliMatcher(
        tahsilat, customers, MappingStore(tmp_path / "same_vkn_chain.json"),
        region_branch_aliases={"DENIZLI": ("DENIZLI",)},
    )

    result = matcher.match(_manim("TED.CAR. - ORNEK ZINCIR 1000000001", 600.0), "DENIZLI")

    assert result is not None
    assert {(row.musteri_kodu, row.tutar) for row in result} == {
        ("C-AYDIN", 100.0), ("C-NAZILLI", 200.0), ("C-DENIZLI", 300.0),
    }


def test_zincir_odemesi_fazlaysa_tum_vkn_subeleri_manuel_oneriye_gelir(tmp_path):
    """Banka tutarı borçtan yüksek olsa da hiçbir zincir şubesi gizlenmez.

    Muğla hareketinde aynı VKN'li Bodrum satırı bölge filtresi nedeniyle
    dışarıda kalıyordu. Otomatik aktarım yapılmaz, ancak manuel ekrana bütün
    tahsilatlar önerilir ve kullanıcı yalnız borç kadarını onaylayabilir.
    """
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("C-BODRUM", "MEYUS DENIZLI KURUYEMIS", "1000000009", "SIMSEK-BODRUM", "MEYUS BODRUM"),
        CustomerRecord("C-MARMARIS-1", "MEYUS DENIZLI KURUYEMIS", "1000000009", "SIMSEK-MARMARIS", "MEYUS - 1"),
        CustomerRecord("C-MARMARIS-2", "MEYUS DENIZLI KURUYEMIS", "1000000009", "SIMSEK-MARMARIS", "MEYUS - 2"),
    ]
    tahsilat = [
        TahsilatRecord("C-BODRUM", "MEYUS BODRUM", None, 12410.00),
        TahsilatRecord("C-MARMARIS-1", "MEYUS - 1", None, 100000.00),
        TahsilatRecord("C-MARMARIS-2", "MEYUS - 2", None, 90005.68),
    ]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "meyus_candidates.json"),
        region_branch_aliases={"MUGLA": ("MARMARIS", "MUGLA")},
    )

    assert matcher.match(_manim("FAST-MEYUS DENIZLI 1000000009", 272924.75), "MUGLA") is None
    assert {(row.musteri_kodu, row.tutar) for row in matcher.last_candidate_rows} == {
        ("C-BODRUM", 12410.00),
        ("C-MARMARIS-1", 100000.00),
        ("C-MARMARIS-2", 90005.68),
    }


def test_zincir_genel_kelime_alakasiz_musterileri_getirmez(tmp_path):
    """'TURZ' gibi onlarca şirkette geçen genel bir kelime zincir belirteci
    sayılmamalı; aksi halde alakasız şirketler yanlışlıkla havuza girer."""
    from app.models.records import CustomerRecord

    # TURZ kelimesi 20'den fazla farkli (MAX_CHAIN_TOKEN_GROUPS'u asan) alakasiz
    # sirkette geciyor - bunlarin hicbiri zincire dahil edilmemeli.
    unrelated = [
        CustomerRecord(f"C-UNREL-{i}", f"FIRMA {i} GIDA TURZ.TIC.LTD.STI.", f"TEST-VKN-{i:02d}", "SIMSEK-MARMARIS", "")
        for i in range(20)
    ]
    customers = [
        CustomerRecord("C-TARGET", "ORNEK PAZARLAMA GIDA TURZ.TIC.LTD.STI.ZETA MARKET 1", "1000000001", "SIMSEK-MARMARIS", ""),
    ] + unrelated
    tahsilat = [
        TahsilatRecord("C-TARGET", "ZETA MARKET 1", None, 1000.0),
    ] + [
        TahsilatRecord(f"C-UNREL-{i}", "ALAKASIZ", None, 50000.0) for i in range(20)
    ]
    matcher = SubeliMatcher(
        tahsilat, customers, MappingStore(tmp_path / "test_mapping_tabela_chain_generic.json"),
        region_branch_aliases={"MUGLA": ("MARMARIS", "MUGLA")},
    )

    # Banka tutari C-TARGET'in kendi tahsilatiyla (1000.0) zaten tutuyor,
    # bu yuzden zincir mekanizmasina hic girmemesi beklenir; asil kontrol,
    # farkli bir tutar denendiginde alakasiz musterilerin katilmamasidir.
    result = matcher.match(_manim("CEP ŞUBE-HVL- -ORNEK PAZARLAMA 1000000001 TR000...", 51000.0), "MUGLA")
    assert result is None  # tek bir alakasiz musteriyle (50000) tesadufen tutan bir toplam olsa bile eslesmemeli


def test_eslesme_bulunamazsa_none_doner(tmp_path):
    tahsilat = [TahsilatRecord(musteri_kodu="C001", musteri_ismi="TAMAMEN ALAKASIZ ISIM", belge_tarihi=None, tutar=500.0)]
    matcher = SubeliMatcher(tahsilat, [], MappingStore(tmp_path / "test_mapping_3.json"))
    assert matcher.match(_manim("BILINMEYEN ACIKLAMA", 999.0)) is None


def test_hafiza_tek_kod_formati(tmp_path):
    store = MappingStore(tmp_path / "mapping.json")
    store.set("TEKRARLANAN ACIKLAMA", "C999")
    matcher = SubeliMatcher([], [], store)
    result = matcher.match(_manim("TEKRARLANAN ACIKLAMA", 250.0))
    assert result is not None
    assert result[0].musteri_kodu == "C999"
    assert result[0].tutar == 250.0


def test_hafiza_bolunmus_kod_formati(tmp_path):
    store = MappingStore(tmp_path / "mapping.json")
    store.set("SUBELI ACIKLAMA", [
        {"musteri_kodu": "C001", "tutar": 100.0},
        {"musteri_kodu": "C002", "tutar": 200.0},
    ])
    matcher = SubeliMatcher([], [], store)
    result = matcher.match(_manim("SUBELI ACIKLAMA", 300.0))
    assert result is not None
    assert {(row.musteri_kodu, row.tutar) for row in result} == {("C001", 100.0), ("C002", 200.0)}


def test_zincir_firma_isimden_bulunur_ve_bolgeye_ait_subeler_seçilir(tmp_path):
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("F001", "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S.", "1000000006", "SIMSEK-FETHIYE"),
        CustomerRecord("F002", "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S.", "1000000006", "SIMSEK-FETHIYE"),
        CustomerRecord("M001", "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S.-MUGLA", "1000000006", "SIMSEK-MARMARIS"),
    ]
    tahsilat = [
        TahsilatRecord("F001", "ORNEK ZINCIR FETHIYE 1", None, 100.0),
        TahsilatRecord("F002", "ORNEK ZINCIR FETHIYE 2", None, 200.0),
        TahsilatRecord("M001", "ORNEK ZINCIR MUGLA", None, 300.0),
    ]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_region_name.json"),
        region_branch_aliases={"FETHIYE": ("FETHIYE",), "MUGLA": ("MARMARIS",)},
    )

    result = matcher.match(_manim("Para Transferi Hesap ORNEK ZINCIR GIDA PAZARLAMA", 300.0), "FETHIYE")

    assert result is not None
    assert {row.musteri_kodu for row in result} == {"F001", "F002"}


def test_isim_yoksa_vergi_numarasindan_subeli_eslesir(tmp_path):
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("H001", "DENEME MAGAZALARI GIDA PAZARLAMA A.S.", "1000000005", "SIMSEK-FETHIYE"),
        CustomerRecord("H002", "DENEME MAGAZALARI GIDA PAZARLAMA A.S.", "1000000005", "SIMSEK-FETHIYE"),
    ]
    tahsilat = [
        TahsilatRecord("H001", "DENEME MAGAZALARI 1", None, 153397.75),
        TahsilatRecord("H002", "DENEME MAGAZALARI 2", None, 200000.00),
    ]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_tax.json"),
        region_branch_aliases={"FETHIYE": ("FETHIYE",)},
    )

    result = matcher.match(_manim("TICARI ODEME 1000000005 TR000000000000000000000000", 353397.75), "FETHIYE")

    assert result is not None
    assert {row.musteri_kodu for row in result} == {"H001", "H002"}


def test_basta_sifiri_dusmus_vergi_numarasi_da_eslesir(tmp_path):
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("S001", "ORNEK TEMIZLIK MAGAZASI", "0111111111", "SIMSEK-KUSADASI"),
    ]
    tahsilat = [TahsilatRecord("S001", "ORNEK TEMIZLIK SUBE", None, 97083.50)]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_leading_zero_tax.json"),
        region_branch_aliases={"SOKE": ("KUSADASI",)},
    )

    result = matcher.match(_manim("TEST LTD STI ORNEK TEMIZLIK 111111111 TR0000000", 97083.50), "SOKE")

    assert result is not None
    assert result[0].musteri_kodu == "S001"




def test_vergi_no_bolge_unvan_koprusu_kodlar_farkli_olsa_da_eslestirir(tmp_path):
    """İş kuralı: VKN -> müşteri listesi -> bölge -> ad -> tahsilat."""
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord(
            "ANA-F-001",
            "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S. FETHIYE 1",
            "1000000006",
            "SIMSEK-FETHIYE",
            "ORNEK ZINCIR FETHIYE MAGAZA 1",
        ),
        CustomerRecord(
            "ANA-F-002",
            "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S. FETHIYE 2",
            "1000000006",
            "SIMSEK-FETHIYE",
            "ORNEK ZINCIR FETHIYE MAGAZA 2",
        ),
        CustomerRecord(
            "ANA-M-001",
            "ORNEK ZINCIR GIDA PAZARLAMA SANAYI VE TICARET A.S. MUGLA 1",
            "1000000006",
            "SIMSEK-MARMARIS",
            "ORNEK ZINCIR MUGLA MAGAZA 1",
        ),
    ]
    # Tahsilat kodları müşteri ana listesindeki kodlardan bilerek farklıdır.
    tahsilat = [
        TahsilatRecord("NET-F-101", "ORNEK ZINCIR FETHIYE MAGAZA 1", None, 100000.00),
        TahsilatRecord("NET-F-102", "ORNEK ZINCIR FETHIYE MAGAZA 2", None, 102985.25),
        TahsilatRecord("NET-M-201", "ORNEK ZINCIR MUGLA MAGAZA 1", None, 104190.50),
    ]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_tax_region_name_bridge.json"),
        region_branch_aliases={"FETHIYE": ("FETHIYE",), "MUGLA": ("MARMARIS", "MUGLA")},
    )

    fethiye = matcher.match(
        _manim("PARA TRANSFERI HESAP ORNEK ZINCIR 1000000006", 202985.25),
        "FETHIYE",
    )
    mugla = matcher.match(
        _manim("PARA TRANSFERI HESAP ORNEK ZINCIR 1000000006", 104190.50),
        "MUGLA",
    )

    assert fethiye is not None
    assert {row.musteri_kodu for row in fethiye} == {"NET-F-101", "NET-F-102"}
    assert mugla is not None
    assert [row.musteri_kodu for row in mugla] == ["NET-M-201"]


def test_vergi_no_tek_subede_bulunuyorsa_manim_bolgesi_farkli_olsa_da_eslesir(tmp_path):
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("B001", "ZINCIR FIRMA BODRUM", "1000000007", "SIMSEK-BODRUM"),
        CustomerRecord("M999", "BASKA FIRMA MUGLA", "1000000008", "SIMSEK-MARMARIS"),
    ]
    tahsilat = [TahsilatRecord("B001", "ZINCIR FIRMA BODRUM", None, 116032.50)]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_unique_tax_cross_region.json"),
        region_branch_aliases={"MUGLA": ("MARMARIS", "MUGLA")},
    )

    result = matcher.match(_manim("CARI ODEME 1000000007", 116032.50), "MUGLA")
    assert result is not None
    assert [row.musteri_kodu for row in result] == ["B001"]


def test_vergi_no_birden_fazla_bolgede_ve_islem_bolgesi_yoksa_global_secmez(tmp_path):
    from app.models.records import CustomerRecord

    customers = [
        CustomerRecord("B001", "ZINCIR FIRMA BODRUM", "1000000007", "SIMSEK-BODRUM"),
        CustomerRecord("F001", "ZINCIR FIRMA FETHIYE", "1000000007", "SIMSEK-FETHIYE"),
    ]
    tahsilat = [
        TahsilatRecord("B001", "ZINCIR FIRMA BODRUM", None, 100.0),
        TahsilatRecord("F001", "ZINCIR FIRMA FETHIYE", None, 100.0),
    ]
    matcher = SubeliMatcher(
        tahsilat,
        customers,
        MappingStore(tmp_path / "test_mapping_ambiguous_tax_region.json"),
        region_branch_aliases={"MUGLA": ("MARMARIS", "MUGLA")},
    )

    assert matcher.match(_manim("CARI ODEME 1000000007", 100.0), "MUGLA") is None
    assert "birden fazla bölgede" in matcher.last_failure_reason


def test_bir_kurus_yuvarlama_farki_float_hatasina_takilmaz():
    rows = [
        TahsilatRecord("C001", "TEST 1", None, 68616.75),
        TahsilatRecord("C002", "TEST 2", None, 83371.50),
    ]
    assert SubeliMatcher._reconciles(151988.24, rows)
