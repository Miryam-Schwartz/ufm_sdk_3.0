#
# Copyright © 2013-2024 NVIDIA CORPORATION & AFFILIATES. ALL RIGHTS RESERVED.
#
# This software product is a proprietary product of Nvidia Corporation and its affiliates
# (the "Company") and all right, title, and interest in and to the software
# product, including all associated intellectual property rights, are and
# shall remain exclusively with the Company.
#
# This software product is governed by the End User License Agreement
# provided with the software product.
#

import argparse
import asyncio
from http import HTTPStatus
import json
import sys
import time

import requests
import hashlib
from datetime import datetime, timedelta

from callback_server import Callback, CallbackServerThread
from ufm_web_service import create_logger

def get_hash(file_content):
    sha1 = hashlib.sha1()
    sha1.update(file_content.encode('utf-8'))
    return sha1.hexdigest()

DEFAULT_PASSWORD = "123456"
DEFAULT_USERNAME = "admin"
NOT_ALLOW="not allowed"
FROM_SOURCES=True

# rest api
GET = "GET"
POST = "POST"

# resources
HELP = "help"
VERSION = "version"
QUERY_REQUEST = "query"
DELETE = "delete"
CANCEL = "cancel"
QUERIES = "queries"
QUERYID = "queries/{}"
DATE = "date"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

FAILED_TESTS_COUNT = 0


# def remove_timestamp(response):
#     if response:
#         if isinstance(response, dict):
#             del response["timestamp"]
#             return response
#         elif isinstance(response, list):
#             return [{i: entry[i] for i in entry if i != "timestamp"} for entry in response]
#         else:
#             return response
#     else:
#         return response


def make_request(request_type, resource, payload=None,
                 user=DEFAULT_USERNAME, password=DEFAULT_PASSWORD,
                 rest_version="", headers=None):
    """ Make request to plugin API """
    Callback.clear_recent_response()
    try:
        if headers is None or payload is None:
            headers = {}

        if not FROM_SOURCES:
            request = f"https://{HOST_IP}/ufmRest{rest_version}/plugin/sysinfo/{resource}"
            auth = (user, password)
        else:
            request = f"http://127.0.0.1:8999/{resource}"
            auth = None

        if request_type == POST:
            response = requests.post(request, verify=False, headers=headers, auth=auth, json=payload, timeout=60)
        elif request_type == GET:
            response = requests.get(request, verify=False, headers=headers, auth=auth, timeout=60)
        else:
            response = None
            print(f"Request {request_type} is not supported")
        return response, f"{request_type} /{resource}"

    except requests.exceptions.ConnectionError:
        response = requests.Response()
        response.status_code = HTTPStatus.NOT_FOUND
        response._content = b"Connection failed" # pylint: disable=protected-access
        return response, f"{request_type} /{resource}"


def check_code(request_str, code, expected_code, test_name="positive"):
    """ Check responsed http code """
    test_type = "code"
    if code == expected_code:
        on_check_success(request_str, test_type, test_name)
    else:
        on_check_fail(request_str, code, expected_code, test_type, test_name)


def check_equal(request_str, left_expr, right_expr, test_name="positive"):
    """ Compare two objects """
    test_type = "response"
    if left_expr == right_expr:
        on_check_success(request_str, test_type, test_name)
    else:
        on_check_fail(request_str, left_expr, right_expr, test_type, test_name)


def check_property(request_str, response, property_name, expected_value, test_name="positive"):
    """ Check value of responsed data property """
    test_type = "response"
    if isinstance(response, dict) and property_name in response and expected_value in response[property_name]:
        on_check_success(request_str, test_type, test_name)
    else:
        on_check_fail(request_str, response, expected_value, test_type, test_name)


def check_length(request_str, response, expected_length, test_name="positive"):
    """ Check responsed dictionary length """
    test_type = "response"
    if isinstance(response, dict) and len(response) == expected_length:
        on_check_success(request_str, test_type, test_name)
    else:
        on_check_fail(request_str, response, f"dictionary of size {expected_length}", test_type, test_name)


def check_commands(request_str, response, expected_switches, expected_command_names, test_name="positive"):
    """ Return True if response contains all requested switches and all requested commands for each switch """
    check_length(request_str, response, len(expected_switches), test_name + " count")
    test_type = "response"
    if not isinstance(response, dict):
        on_check_fail(request_str, response, f"{expected_command_names}", test_type, test_name + " commands")
        return
    for switch_guid, switch_commands in response.items(): # pylint: disable=unused-variable
          command_names = list(switch_commands.keys())
          check_equal(request_str, command_names, expected_command_names, test_name + " commands")


def on_check_success(request_str, test_type, test_name):
    """ Called on successful check """
    print(f"    - test name: {test_name} {test_type}, request: {request_str} -- PASS")


def on_check_fail(request_str, left_expr, right_expr, test_type, test_name):
    """ Called on failed check """
    global FAILED_TESTS_COUNT # pylint: disable=global-statement
    FAILED_TESTS_COUNT += 1
    print(f"    - test name: {test_name} {test_type}, request: {request_str} -- FAIL (expected: {right_expr}, actual: {left_expr})")


def get_response(response):
    """ Return json data from the response """
    if response is not None:
        try:
            json_response = response.json()
            return json_response
        except: # pylint: disable=bare-except
            return response.text
    else:
        return None


def get_code(response):
    """ Return http code from the response"""
    if response is not None:
        return response.status_code
    else:
        return None


async def test_help_and_version():
    """ Help and version query tests """
    print("help and version works")

    response, request_string = make_request(GET, HELP)
    check_code(request_string, get_code(response), HTTPStatus.OK)
    check_length(request_string, get_response(response), 8)

    response, request_string = make_request(GET, VERSION)
    check_code(request_string, get_code(response), HTTPStatus.OK)
    check_length(request_string, get_response(response), 1)

    test_name = NOT_ALLOW
    response, request_string = make_request(POST, HELP)
    check_code(request_string, get_code(response), HTTPStatus.METHOD_NOT_ALLOWED, test_name)
    
    response, request_string = make_request(POST, QUERIES)
    check_code(request_string, get_code(response), HTTPStatus.METHOD_NOT_ALLOWED, test_name)


async def test_instant_query():
    """ Instant query tests """
    print("Run comparison test")
    request = {}
    request['callback'] = Callback.URL

    test_name = NOT_ALLOW
    response, request_string = make_request(GET, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.METHOD_NOT_ALLOWED, test_name)

    test_name = "incorrect praser information"
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Incorrect format, missing keys in request", test_name)

    request['commands'] = ["show power", "show inventory"]
    request['callback'] = f"notURL/{Callback.ROUTE}"

    test_name = "incorrect URL"
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Incorrect callback url format", test_name)

    test_name = "unreachable switches"
    non_existing_ip = "1.2.3.4"
    request['callback'] = Callback.URL
    request['switches'] = [non_existing_ip]

    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    data_from = await Callback.wait_for_response(10)
    check_code(request_string, get_code(response), HTTPStatus.OK, test_name)
    check_property(request_string, data_from, non_existing_ip, "Switch does not respond to ping", test_name)

    test_name = "unrecognized switches"
    non_switch_ip = "127.0.0.1"
    request['callback'] = Callback.URL
    request['switches'] = [non_switch_ip]

    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    data_from = await Callback.wait_for_response(10)
    check_code(request_string, get_code(response), HTTPStatus.OK, test_name)
    check_property(request_string, data_from, non_switch_ip, "Switch does not located on the running ufm", test_name)

    test_name = "valid switches"
    switch_ip = "10.209.227.189"
    request['switches'] = [switch_ip]

    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    data_from = await Callback.wait_for_response(10)
    check_code(request_string, get_code(response), HTTPStatus.OK, test_name)
    check_commands(request_string, data_from, request['switches'], request['commands'], test_name)


def get_server_datetime():
    """ Return server timestamp """
    response, _ = make_request(GET, DATE)
    datetime_response = get_response(response)
    datetime_string = datetime_response["date"]
    return datetime.strptime(datetime_string, DATETIME_FORMAT)


async def test_invalid_periodic_query():
    """ Periodic query tests """
    print("Periodic comparison")

    test_name = "empty request"
    request = {}
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Incorrect format, missing keys in request", test_name)

    test_name = "incorrect request"
    request = {}
    request['callback'] = Callback.URL
    request['switches'] = ["10.209.227.189"]
    request['commands'] = ["show power","show inventory"]
    request["periodic_run"] = {}
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Incorrect format, missing keys in request", test_name)

    test_name = "incorrect datetime format"
    request["periodic_run"] = {
        "startTime": "asd",
        "endTime": "xyz",
        "interval": 10
    }
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Incorrect timestamp format: time data 'asd' does not match format", test_name)

    datetime_end = datetime_start = get_server_datetime() + timedelta(seconds=3)
    test_name = "too small interval"
    request["periodic_run"] = {
        "startTime": datetime_start.strftime(DATETIME_FORMAT),
        "endTime": datetime_end.strftime(DATETIME_FORMAT),
        "interval": 1
    }
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "Minimal interval value is 5 seconds", test_name)

    test_name = "end time less than start time"
    request["periodic_run"] = {
        "startTime": datetime_start.strftime(DATETIME_FORMAT),
        "endTime": (datetime_end - timedelta(seconds=10)).strftime(DATETIME_FORMAT),
        "interval": 10
    }
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.BAD_REQUEST, test_name)
    check_property(request_string, get_response(response), "error", "End time is less than current time", test_name)


async def test_valid_periodic_query():
    """ Valid periodic query """
    # Start periodic query
    test_name = "valid periodic query"
    request = {}
    request['callback'] = Callback.URL
    request['switches'] = ["10.209.227.189"]
    request['commands'] = ["show power","show inventory"]
    datetime_start = get_server_datetime()
    datetime_end = datetime_start + timedelta(minutes=1)
    request["periodic_run"] = {
        "startTime": datetime_start.strftime(DATETIME_FORMAT),
        "endTime": datetime_end.strftime(DATETIME_FORMAT),
        "interval": 10
    }
    response, request_string = make_request(POST, QUERY_REQUEST, payload=request)
    check_code(request_string, get_code(response), HTTPStatus.OK)
    check_equal(request_string, get_response(response), {}, test_name)

    # Ckeck query
    if get_code(response) == HTTPStatus.OK:
        # Verify periodic callbacks
        timeout = 15
        for _ in range(6):
            Callback.clear_recent_response()
            data_from = await Callback.wait_for_response(timeout)
            check_commands(request_string, data_from, request["switches"], request["commands"], test_name)

        # Verify that query is stopped on expiration time
        Callback.clear_recent_response()
        data_from = await Callback.wait_for_response(timeout)
        check_equal(request_string, data_from, None, test_name)

async def main():
    """ Main function """
    logger = create_logger("/log/sysinfo_test.log")

    callback_thread = CallbackServerThread(logger)
    callback_thread.start()

    await test_help_and_version()
    await test_instant_query()
    await test_invalid_periodic_query()
    await test_valid_periodic_query()

    await callback_thread.stop()

    if FAILED_TESTS_COUNT > 0:
        logger.error(f"{FAILED_TESTS_COUNT} tests failed")
        return 1
    else:
        logger.info("All tests succeeded")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sysinfo plugin test')
    parser.add_argument('-ip', '--host', type=str, required=True, help='Host IP address where Sysinfo plugin is running')
    args = parser.parse_args()
    HOST_IP = args.host

    result = asyncio.run(main())
    #sys.exit(result)
