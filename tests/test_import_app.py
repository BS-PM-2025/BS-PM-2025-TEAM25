
def test_import_app():
    # simply verify your Flask app object exists
    import run
    assert hasattr(run, "app")