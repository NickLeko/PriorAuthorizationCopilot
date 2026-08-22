from streamlit.testing.v1 import AppTest

APPTEST_TIMEOUT_SECONDS = 10


def test_streamlit_app_loads_without_exceptions():
    at = AppTest.from_file("app.py")

    at.run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any(metric.label == "Supported procedures" and metric.value == "4" for metric in at.metric)
    assert any(subheader.value == "Supported Procedure Registry" for subheader in at.subheader)


def test_streamlit_featured_case_load_produces_results():
    at = AppTest.from_file("app.py")

    at.run(timeout=APPTEST_TIMEOUT_SECONDS)
    if at.checkbox:
        at.checkbox[0].check().run(timeout=APPTEST_TIMEOUT_SECONDS)
    load_buttons = [button for button in at.button if button.label == "Load Demo Case"]
    load_buttons[-1].click().run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any("status-panel" in markdown.value and "CANNOT_DETERMINE" in markdown.value for markdown in at.markdown)
    assert any(markdown.value == "#### Deterministic decision trace" for markdown in at.markdown)


def test_unrelated_drift_does_not_block_unmonitored_featured_case():
    at = AppTest.from_file("app.py")

    at.run(timeout=APPTEST_TIMEOUT_SECONDS)
    cpap_button = next(button for button in at.button if button.key == "case_CPAP-02-borderline")
    cpap_button.click().run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any("status-panel" in markdown.value and "CANNOT_DETERMINE" in markdown.value for markdown in at.markdown)
    assert not any(metric.label == "Overall status" for metric in at.metric)
    assert not any(metric.label == "Documentation coverage" for metric in at.metric)
    assert any(metric.label == "Criteria met" and metric.value == "1 of 3" for metric in at.metric)
    assert any(metric.label == "Missing" and metric.value == "2 missing" for metric in at.metric)
    assert any(metric.label == "Needs review" and metric.value == "0 needs review" for metric in at.metric)
    assert any(markdown.value == "“OSA”" for markdown in at.markdown)
    assert any(caption.value == "osa_diagnosis" for caption in at.caption)
    assert any("`equals_true`" in markdown.value for markdown in at.markdown)
    assert any("❌ MISSING" in markdown.value for markdown in at.markdown)
    assert any("resolve deterministically" in caption.value and "CANNOT_DETERMINE" in caption.value for caption in at.caption)


def test_current_verified_monitored_case_does_not_require_drift_acknowledgement():
    at = AppTest.from_file("app.py")

    at.run(timeout=APPTEST_TIMEOUT_SECONDS)
    lumbar_button = next(button for button in at.button if button.key == "case_MRI-01-complete")
    lumbar_button.click().run(timeout=APPTEST_TIMEOUT_SECONDS)

    assert not at.exception
    assert any('Loaded "Lumbar MRI ready for administrative review" and ran the evaluation.' in message.value for message in at.success)
    assert not any("Acknowledge the drift gate" in message.value for message in at.info)
