def prRed(skk): print("\033[91m{}\033[00m" .format(skk))
def prGreen(skk): print("\033[92m{}\033[00m" .format(skk))
def prYellow(skk): print("\033[93m{}\033[00m" .format(skk))
def prLightPurple(skk): print("\033[94m{}\033[00m" .format(skk))
def prPurple(skk): print("\033[95m{}\033[00m" .format(skk))
def prCyan(skk): print("\033[96m{}\033[00m" .format(skk))
def prLightGray(skk): print("\033[97m{}\033[00m" .format(skk))
def prBlack(skk): print("\033[98m{}\033[00m" .format(skk))

def assert_string_type(value, description):
    """Helper function to check if value is a string and print result"""
    if isinstance(value, str):
        prGreen(f"PASS: {description} returned as string")
    else:
        prRed(f"FAIL: {description} not returned as string. Got type: {type(value)}")

def assert_bool_type(value, description):
    """Helper function to check if value is a boolean and print result"""
    if isinstance(value, bool):
        prGreen(f"PASS: {description} returned as boolean")
    else:
        prRed(f"FAIL: {description} not returned as boolean. Got type: {type(value)}")

def assert_int_type(value, description):
    """Helper function to check if value is an integer and print result"""
    if isinstance(value, int):
        prGreen(f"PASS: {description} returned as integer")
    else:
        prRed(f"FAIL: {description} not returned as integer. Got type: {type(value)}")

def assert_list_type(value, description):
    """Helper function to check if value is a list and print result"""
    if isinstance(value, list):
        prGreen(f"PASS: {description} returned as list")
    else:
        prRed(f"FAIL: {description} not returned as list. Got type: {type(value)}")

def assert_object_type(value, description, expected_class=None):
    """
    Helper function to check if value is an object of expected_class
    If expected_class is None, checks if value is any object
    """
    if expected_class:
        if isinstance(value, expected_class):
            prGreen(f"PASS: {description} returned as {expected_class.__name__} object")
        else:
            prRed(f"FAIL: {description} not returned as {expected_class.__name__} object. Got type: {type(value)}")
    else:
        # Check if it's any object but not a primitive type
        primitive_types = (str, int, float, bool, list, dict, tuple, set)
        if isinstance(value, object) and not isinstance(value, primitive_types):
            prGreen(f"PASS: {description} returned as object")
        else:
            prRed(f"FAIL: {description} not returned as object. Got type: {type(value)}")


def assert_json_type(value, description):
    """
    Simple helper function to check if value is a valid JSON object
    """
    # First check if it's a dict
    if not isinstance(value, dict):
        prRed(f"FAIL: {description} not a valid JSON object. Got type: {type(value)}")
        return False

    # Check if all values are JSON serializable
    def is_json_serializable(obj):
        basic_types = (str, int, float, bool, type(None))
        if isinstance(obj, basic_types):
            return True
        elif isinstance(obj, (list, tuple)):
            return all(is_json_serializable(item) for item in obj)
        elif isinstance(obj, dict):
            return all(isinstance(k, str) and is_json_serializable(v) for k, v in obj.items())
        return False

    if is_json_serializable(value):
        prGreen(f"PASS: {description} is a valid JSON object")
        return True
    else:
        prRed(f"FAIL: {description} contains non-JSON-serializable values")
        return False