from app import sysinfo


def test_dxf_guard_scales_with_memory(monkeypatch):
    monkeypatch.setenv("MEMORY_LIMIT_MB", "512")
    assert sysinfo.memory_limit_mb() == 512
    assert sysinfo.max_dxf_mb() == round((512 - 180) / 25, 1)
    assert sysinfo.dxf_too_large(int(20.6e6)) is not None      # the JVT file on a 512 MB box
    assert sysinfo.dxf_too_large(int(5e6)) is None
    monkeypatch.setenv("MEMORY_LIMIT_MB", "2048")
    assert sysinfo.dxf_too_large(int(20.6e6)) is None           # fine on 2 GB
