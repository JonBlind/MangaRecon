import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from backend.utils.errors import register_exception_handlers

class Payload(BaseModel):
    # just a simple integer.
    # integer should be >= 0 else it should fail.
    value: int = Field(ge=0)

@pytest.fixture(scope="module")
def app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-http")
    def raise_http():
        # Simulate 403 err
        raise HTTPException(status_code=403, detail="Forbidden")
    
    @app.get("/raise-any")
    def raise_any():
        # Unhandled error
        raise RuntimeError("Kablamo")
    
    @app.post("/validate")
    def validate(payload: Payload):
        return {"Good" : payload.value}

    return app
    
@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)
    
class TestHTTPExceptionHandler:
    def test_http_exception_return(self, client, caplog):
            with caplog.at_level("WARNING", logger="backend.utils.errors"):
                response = client.get("/raise-http")
    
            assert response.status_code == 403
            response_body = response.json()

            assert response_body.keys() == {"status", "data", "message", "detail"}
            assert response_body["status"] == "error"
            assert response_body["message"] == "Error"
            assert response_body["detail"] == "Forbidden"
            assert response_body["data"] == {}
            assert any("http error:" in rec.message for rec in caplog.records)
    
class TestValidationHandler:
    def test_validation_error_422(self, client):
            response = client.post("/validate", json={"value": "this aint no int"})
            assert response.status_code == 422
            response_body = response.json()

            assert response_body.keys() == {"status", "data", "message", "detail"}
            assert response_body["status"] == "error"
            assert response_body["message"] == "Validation error"
            assert isinstance(response_body["detail"], list) and len(response_body["detail"]) >= 1
            assert response_body["data"] == {}
    
    def test_validation_logs_and_hits_handler(self, client, caplog):
        with caplog.at_level("WARNING", logger="backend.utils.errors"):
            response = client.post("/validate", json={"value": -1})

        assert response.status_code == 422
        response_body = response.json()
        assert response_body.keys() == {"status", "data", "message", "detail"}
        assert response_body["status"] == "error"
        assert response_body["message"] == "Validation error"
        assert response_body["data"] == {}
        assert isinstance(response_body["detail"], list) and len(response_body["detail"]) >= 1
        
class TestUnexpectedHandler:
    def test_unhandled_maps_500(self, client, caplog):
            with caplog.at_level("ERROR", logger="backend.utils.errors"):
                response = client.get("/raise-any")

            assert response.status_code == 500
            response_body = response.json()

            assert response_body.keys() == {"status", "data", "message", "detail"}
            assert response_body["status"] == "error"
            assert response_body["message"] == "Internal server error"
            assert response_body["detail"] == "An unexpected error occurred"
            assert response_body["data"] == {}
            
            assert any("unhandled:" in rec.message for rec in caplog.records)
