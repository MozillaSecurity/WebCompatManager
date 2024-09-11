import logging

import pytest
import requests

LOG = logging.getLogger("fm.reportmanager.tests.bugproviders.rest")


@pytest.mark.parametrize("method", ["delete", "get", "patch", "post", "put"])
def test_rest_bugproviders_no_auth(db, api_client, method):
    """must yield unauthorized without authentication"""
    assert (
        getattr(api_client, method)("/reportmanager/rest/bugproviders/", {}).status_code
        == requests.codes["unauthorized"]
    )


@pytest.mark.parametrize("method", ["delete", "get", "patch", "post", "put"])
@pytest.mark.parametrize("user", ["noperm", "only_sigs", "only_report"], indirect=True)
def test_rest_bugproviders_no_perm(user, api_client, method):
    """must yield forbidden without permission"""
    assert (
        getattr(api_client, method)("/reportmanager/rest/bugproviders/", {}).status_code
        == requests.codes["forbidden"]
    )


@pytest.mark.parametrize(
    "method, url, user",
    [
        ("delete", "/reportmanager/rest/bugproviders/", "normal"),
        ("delete", "/reportmanager/rest/bugproviders/", "restricted"),
        ("patch", "/reportmanager/rest/bugproviders/", "normal"),
        ("patch", "/reportmanager/rest/bugproviders/", "restricted"),
        ("post", "/reportmanager/rest/bugproviders/", "normal"),
        ("post", "/reportmanager/rest/bugproviders/", "restricted"),
        ("put", "/reportmanager/rest/bugproviders/", "normal"),
        ("put", "/reportmanager/rest/bugproviders/", "restricted"),
    ],
    indirect=["user"],
)
def test_rest_bugproviders_methods(api_client, user, method, url):
    """must yield method-not-allowed for unsupported methods"""
    assert (
        getattr(api_client, method)(url, {}).status_code
        == requests.codes["method_not_allowed"]
    )


@pytest.mark.parametrize(
    "method, url, user",
    [
        ("get", "/reportmanager/rest/bugproviders/1/", "normal"),
        ("get", "/reportmanager/rest/bugproviders/1/", "restricted"),
        ("delete", "/reportmanager/rest/bugproviders/1/", "normal"),
        ("delete", "/reportmanager/rest/bugproviders/1/", "restricted"),
        ("patch", "/reportmanager/rest/bugproviders/1/", "normal"),
        ("patch", "/reportmanager/rest/bugproviders/1/", "restricted"),
        ("post", "/reportmanager/rest/bugproviders/1/", "normal"),
        ("post", "/reportmanager/rest/bugproviders/1/", "restricted"),
        ("put", "/reportmanager/rest/bugproviders/1/", "normal"),
        ("put", "/reportmanager/rest/bugproviders/1/", "restricted"),
    ],
    indirect=["user"],
)
def test_rest_bugproviders_methods_not_found(api_client, user, method, url):
    """must yield not-found for undeclared methods"""
    assert (
        getattr(api_client, method)(url, {}).status_code == requests.codes["not_found"]
    )


def _compare_rest_result_to_bugprovider(result, provider):
    expected_fields = {"id", "classname", "hostname", "urlTemplate"}
    assert set(result) == expected_fields
    for key, value in result.items():
        assert value == getattr(provider, key)


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
def test_rest_bugproviders_list(api_client, user, cm):
    """test that list returns the right bug providers"""
    expected = 4
    providers = [
        cm.create_bugprovider(
            hostname="test-provider%d.com" % (i + 1),
            urlTemplate="test-provider%d.com/template" % (i + 1),
        )
        for i in range(expected)
    ]
    resp = api_client.get("/reportmanager/rest/bugproviders/")
    LOG.debug(resp)
    assert resp.status_code == requests.codes["ok"]
    resp = resp.json()
    assert set(resp) == {"count", "next", "previous", "results"}
    assert resp["count"] == expected
    assert resp["next"] is None
    assert resp["previous"] is None
    assert len(resp["results"]) == expected
    for result, provider in zip(resp["results"], providers[:expected]):
        _compare_rest_result_to_bugprovider(result, provider)