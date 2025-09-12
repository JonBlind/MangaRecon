from typing import Any, Optional


def success(message:str, data: Optional[dict] = None) -> dict:
    '''
    Wrapper for successful responses.
    Args:
        message (Str): Message to print/return indicating state of the response. Required since each official request should have an associated message.
        data (Dict [Optional]): data/payload to return as a sign of success.
    Returns:
        dict: A dictionary containing response information based on the following keys:
            - 'status' (str) : 'success' representing state of response
            - 'data' (dict) : Returned payload from the response or proof of success. If nothing returns, it will just be an empty Dict.
            - 'message' (str): Message summarizing the response.
            - 'detail' (None) : FOR SUCCESSES. No details should be returned as this field is used for error strings.

    '''
    if not message:
        raise ValueError("Response Message CAN NOT be EMPTY")

    return {
        "status" : "success",
        "data" : data or {},
        "message" : message,
        "detail" : None
    }

def error(message:str, detail:str, data: Optional[dict] = None) -> dict:
    '''
    Wrapper for error/failed responses.
    Args:
        message (Str): Message to print/return indicating state of the response. Required since each official request should have an associated message.
        detail (Str): Message associated with the error. Likely just the string of the associated catched error.
        data (Dict [Optional]): data/payload to return.

    Returns:
        dict: A dictionary containing response information based on the following keys:
            - 'status' (str) : 'error' representing state of response
            - 'data' (dict) : Returned payload from the response or proof of success. If nothing returns, it will just be an empty Dict.
            - 'message' (str): Message summarizing the response.
            - 'detail' (str) : Information relating to the error that occurred. Likely the caught error as a string.
    '''

    if not message:
        raise ValueError("Response Message CAN NOT be EMPTY")
    
    elif not detail:
        raise ValueError("Detail Field CAN NOT be EMPTY for errors")
    
    return {
        "status" : "error",
        "data" : data or {},
        "message" : message,
        "detail" : detail
    }