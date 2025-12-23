import pytest
from backend.utils import response

class TestError:
    def test_missing_data_field(self):
        output = response.error("Bad request", "Missing field", data={"field": "name"})
        assert isinstance(output, dict)
        assert output.keys() == {"status", "data", "message", "detail"}
        assert output["status"] == "error"
        assert output["message"] == "Bad request"
        assert output["detail"] == "Missing field"
        assert output["data"] == {"field": "name"}

    def test_defaults_data_to_empty_dict(self):
        output = response.error("Bad request", "Missing field")
        assert output["data"] == {}

    def test_rejects_empty_message(self):
        with pytest.raises(ValueError) as err:
            response.error("", "x")

        assert "Response Message CAN NOT be EMPTY" in str(err.value)

    def test_rejects_empty_detail(self):
        with pytest.raises(ValueError) as err:
            response.error("whoops", "")
        assert "Detail Field CAN NOT be EMPTY for errors" in str(err.value)

class TestSuccess:
    def test_good_response(self):
        output = response.success("Good Test", data={"id" : 1})
        assert isinstance(output, dict)
        assert output.keys() == {"status", "data", "message", "detail"}
        assert output["status"] == "success"
        assert output["message"] == "Good Test"
        assert output["data"] == {"id" : 1}

    def test_defaults_data_to_empty_dict(self):
        output = response.success("Bad request")
        assert output["data"] == {}

    def test_rejects_empty_message(self):
        with pytest.raises(ValueError) as err:
            response.success("", "x")

        assert "Response Message CAN NOT be EMPTY" in str(err.value)