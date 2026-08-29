from app.ui.manual_match_dialog import ManualMatchDialog


def test_turkce_binlik_ayracli_tutar_dogru_okunur():
    # Gercek hatanin sebebi: '7.831,00' -> naif .replace(',', '.') ile
    # '7.831.00' (gecersiz) oluyordu ve satir sessizce atlaniyordu.
    assert ManualMatchDialog._parse_amount("7.831,00") == 7831.00
    assert ManualMatchDialog._parse_amount("33.950,25") == 33950.25
    assert ManualMatchDialog._parse_amount("136.135,25") == 136135.25


def test_binlik_ayraci_olmayan_tutarlar_da_dogru_okunur():
    assert ManualMatchDialog._parse_amount("7831,00") == 7831.00
    assert ManualMatchDialog._parse_amount("7831.00") == 7831.00
    assert ManualMatchDialog._parse_amount("7831") == 7831.0


def test_bos_veya_gecersiz_tutar_none_doner():
    assert ManualMatchDialog._parse_amount("") is None
    assert ManualMatchDialog._parse_amount("abc") is None
