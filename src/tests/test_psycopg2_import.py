def test_psycopg2_import():
    import psycopg2
    from packaging.version import parse
    print('psycopg2 version:', psycopg2.__version__)
    version = psycopg2.__version__.split()[0]
    assert parse(version) >= parse('2.9.9') 