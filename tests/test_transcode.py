from kjsync import transcode

ENCODERS_SAMPLE = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264
 V....D libx265              libx265 H.265 / HEVC (codec hevc)
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)
 V..... hevc_qsv             HEVC (Intel Quick Sync) (codec hevc)
 A....D aac                  AAC
"""


def test_parse_hevc_encoders():
    enc = transcode.parse_hevc_encoders(ENCODERS_SAMPLE)
    assert "libx265" in enc
    assert "hevc_nvenc" in enc
    assert "hevc_qsv" in enc
    assert "libx264" not in enc
    assert "aac" not in enc


def test_choose_encoder_auto_prefers_hardware():
    assert transcode.choose_encoder("auto", ["libx265", "hevc_nvenc"]) == "hevc_nvenc"
    assert transcode.choose_encoder("auto", ["libx265"]) == "libx265"
    assert transcode.choose_encoder("auto", []) is None


def test_choose_encoder_specific_and_fallback():
    assert transcode.choose_encoder("nvenc", ["hevc_nvenc", "libx265"]) == "hevc_nvenc"
    assert transcode.choose_encoder("libx265", ["libx265"]) == "libx265"
    # pedido no disponible -> fallback al mejor disponible
    assert transcode.choose_encoder("qsv", ["libx265"]) == "libx265"


def test_quality_args_per_encoder():
    assert transcode.quality_args("libx265", 23, 28, None)[:2] == ["-c:v", "libx265"]
    assert "-crf" in transcode.quality_args("libx265", 23, 28, None)
    nv = transcode.quality_args("hevc_nvenc", 23, 28, None)
    assert nv[:2] == ["-c:v", "hevc_nvenc"]
    assert "-cq" in nv


def test_build_ffmpeg_cmd():
    cmd = transcode.build_ffmpeg_cmd("in.mp4", "out.mp4", "libx265", crf=20)
    assert cmd[0] == "ffmpeg" and "-i" in cmd and cmd[-1] == "out.mp4"
    assert "in.mp4" in cmd
    assert "-c:a" in cmd and "copy" in cmd
    assert "20" in cmd  # crf value
    cmd2 = transcode.build_ffmpeg_cmd("in.mp4", "out.mp4", "libx265", metadata_args=["-metadata", "title=X"])
    assert "title=X" in cmd2


def test_output_name_and_idempotency():
    assert transcode.output_name("01 - Intro.mp4", "h265") == "01 - Intro [h265].mp4"
    assert transcode.already_transcoded("01 - Intro [h265].mp4", "h265") is True
    assert transcode.already_transcoded("01 - Intro.mp4", "h265") is False


def test_parse_path_metadata():
    meta = transcode.parse_path_metadata("Curso X/Bloque 1/03 - La leccion.mp4")
    assert meta["course"] == "Curso X"
    assert meta["block"] == "Bloque 1"
    assert meta["track"] == "03"
    assert meta["title"] == "La leccion"


def test_build_metadata_args():
    args = transcode.build_metadata_args({"course": "C", "block": "B", "track": "3", "title": "T"})
    assert "-metadata" in args
    assert "title=T" in args
    assert "album=C" in args


def test_plan_tree_classifies():
    files = ["a/01 - v.mp4", "a/02 - v [h265].mp4", "a/doc.pdf"]
    plan = transcode.plan_tree(files, transcode.VIDEO_EXTS, "h265")
    assert plan["transcode"] == ["a/01 - v.mp4"]
    assert plan["skip"] == ["a/02 - v [h265].mp4"]
    assert plan["copy"] == ["a/doc.pdf"]


def test_is_ffmpeg_available_returns_bool():
    assert isinstance(transcode.is_ffmpeg_available(), bool)
