from streamlit.testing.v1 import AppTest


def test_streamlit_app_loads_without_exceptions():
    at = AppTest.from_file("app.py")

    at.run()

    assert not at.exception
    assert any(metric.label == "Supported procedures" and metric.value == "4" for metric in at.metric)
    assert any(subheader.value == "Supported Procedure Registry" for subheader in at.subheader)


def test_streamlit_featured_case_load_produces_results():
    at = AppTest.from_file("app.py")

    at.run()
    if at.checkbox:
        at.checkbox[0].check().run()
    load_buttons = [button for button in at.button if button.label == "Load Demo Case"]
    load_buttons[-1].click().run()

    assert not at.exception
    assert any(metric.label == "Overall status" for metric in at.metric)
