"""Tests for Buckets rest api.

@author:     Jesse Schwartzentruber (:truber)

@license:

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
import json
import logging

import pytest
import requests
from django.urls import reverse
from rest_framework import status

from reportmanager.models import Bucket, Bug, ReportEntry

from .conftest import _create_user

# What should be allowed:
#
# +--------+------+----------+---------+---------+--------------+-------------------+
# |        |      |          | no auth | no perm | unrestricted | unrestricted      |
# |        |      |          |         |         |              | ignore_toolfilter |
# +--------+------+----------+---------+---------+--------------+-------------------+
# | GET    | /    | list     | 401     | 403     | toolfilter   | all               |
# |        +------+----------+---------+---------+--------------+-------------------+
# |        | /id/ | retrieve | 401     | 403     | all          | all               |
# +--------+------+----------+---------+---------+--------------+-------------------+
# | POST   | /    | create   | 401     | 403     | all          | all (TODO)        |
# |        +------+----------+---------+---------+--------------+-------------------+
# |        | /id/ | -        | 401     | 403     | 405          | 405               |
# +--------+------+----------+---------+---------+--------------+-------------------+
# | PUT    | /    | -        | 401     | 403     | 405          | 405               |
# |        +------+----------+---------+---------+--------------+-------------------+
# |        | /id/ | -        | 401     | 403     | 405          | 405               |
# +--------+------+----------+---------+---------+--------------+-------------------+
# | PATCH  | /    | -        | 401     | 403     | 405          | 405               |
# |        +------+----------+---------+---------+--------------+-------------------+
# |        | /id/ | update   | 401     | 403     | all          | all               |
# +--------+------+----------+---------+---------+--------------+-------------------+
# | DELETE | /    | -        | 401     | 403     | 405          | 405               |
# |        +------+----------+---------+---------+--------------+-------------------+
# |        | /id/ | delete   | 401     | 403     | all (TODO)   | all (TODO)        |
# +--------+------+----------+---------+---------+--------------+-------------------+
#
# +--------+------+----------+------------+-------------------+
# |        |      |          | restricted | restricted        |
# |        |      |          |            | ignore_toolfilter |
# +--------+------+----------+------------+-------------------+
# | GET    | /    | list     | toolfilter | toolfilter        |
# |        +------+----------+------------+-------------------+
# |        | /id/ | retrieve | toolfilter | toolfilter        |
# +--------+------+----------+------------+-------------------+
# | POST   | /    | create   | all        | all (TODO)        |
# |        +------+----------+------------+-------------------+
# |        | /id/ | -        | 405        | 405               |
# +--------+------+----------+------------+-------------------+
# | PUT    | /    | -        | 405        | 405               |
# |        +------+----------+------------+-------------------+
# |        | /id/ | -        | 405        | 405               |
# +--------+------+----------+------------+-------------------+
# | PATCH  | /    | -        | 405        | 405               |
# |        +------+----------+------------+-------------------+
# |        | /id/ | update   | 405        | 405               |
# +--------+------+----------+------------+-------------------+
# | DELETE | /    | -        | 405        | 405               |
# |        +------+----------+------------+-------------------+
# |        | /id/ | delete   | 405        | 405               |
# +--------+------+----------+------------+-------------------+


LOG = logging.getLogger("fm.reportmanager.tests.signatures.rest")


def _compare_rest_result_to_bucket(
    result, bucket, size, quality, best_entry=None, latest=None, hist=[], vue=False
):
    attributes = {
        "best_entry",
        "best_quality",
        "bug",
        "doNotReduce",
        "frequent",
        "id",
        "permanent",
        "shortDescription",
        "signature",
        "size",
        "has_optimization",
        "latest_entry",
    }
    if vue:
        attributes.update(
            {
                "view_url",
                "opt_pre_url",
                "bug_closed",
                "bug_urltemplate",
                "bug_hostname",
                "report_history",
            }
        )

    assert set(result) == attributes
    assert result["id"] == bucket.pk
    assert result["best_quality"] == quality
    assert result["best_entry"] == best_entry
    assert result["doNotReduce"] == bucket.doNotReduce
    assert result["latest_entry"] == latest
    assert result["bug"] == bucket.bug_id
    assert result["frequent"] == bucket.frequent
    assert result["has_optimization"] == bool(bucket.optimizedSignature)
    assert result["permanent"] == bucket.permanent
    assert result["shortDescription"] == bucket.shortDescription
    assert result["signature"] == bucket.signature
    assert result["size"] == size
    if vue:
        assert result["view_url"] == reverse(
            "reportmanager:sigview", kwargs={"sigid": bucket.pk}
        )
        assert result["opt_pre_url"] == reverse(
            "reportmanager:sigoptpre", kwargs={"sigid": bucket.pk}
        )
        assert result["bug_closed"] is None
        assert result["bug_urltemplate"] is None
        assert result["bug_hostname"] is None
        # sanitize timestamp before comparing
        result_report_history = [entry.copy() for entry in result["report_history"]]
        for idx, entry in enumerate(result_report_history):
            entry["begin"] = f"ts{idx}"
        assert result_report_history == hist


@pytest.mark.parametrize("method", ["delete", "get", "patch", "post", "put"])
@pytest.mark.parametrize(
    "url",
    [
        "/reportmanager/rest/buckets/",
        "/reportmanager/rest/buckets/1/",
    ],
)
def test_rest_signatures_no_auth(db, api_client, method, url):
    """must yield unauthorized without authentication"""
    assert (
        getattr(api_client, method)(url, {}).status_code
        == requests.codes["unauthorized"]
    )


@pytest.mark.parametrize("method", ["delete", "get", "patch", "post", "put"])
@pytest.mark.parametrize(
    "url",
    [
        "/reportmanager/rest/buckets/",
        "/reportmanager/rest/buckets/1/",
    ],
)
@pytest.mark.usefixtures("user_noperm")
def test_rest_signatures_no_perm(api_client, method, url):
    """must yield forbidden without permission"""
    assert (
        getattr(api_client, method)(url, {}).status_code == requests.codes["forbidden"]
    )


@pytest.mark.parametrize("method", ["delete", "patch", "post", "put"])
@pytest.mark.parametrize(
    "url",
    [
        "/reportmanager/rest/buckets/1/",
        "/reportmanager/rest/buckets/",
    ],
)
@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
def test_rest_signatures_methods(api_client, user, method, url):
    """must yield method-not-allowed for unsupported methods"""
    if url.endswith("buckets/") and method == "post":
        pytest.skip()
    if url.endswith("1/") and method == "patch" and user.username == "test":
        pytest.skip()
    # TODO: this should be allowed, but hasn't been implemented
    # if url.endswith("1/") and method == "delete" and user.username == "test":
    #     pytest.skip()
    assert (
        getattr(api_client, method)(url, {}).status_code
        == requests.codes["method_not_allowed"]
    )


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
@pytest.mark.parametrize("ignore_toolfilter", [True, False])
@pytest.mark.parametrize("vue", [True, False])
def test_rest_signatures_list(api_client, cm, user, ignore_toolfilter, vue):
    """test that buckets can be listed"""
    bucket1 = cm.create_bucket(shortDescription="bucket #1")
    bucket2 = cm.create_bucket(shortDescription="bucket #2")
    buckets = [bucket1, bucket2, bucket1, bucket1]
    tests = [
        cm.create_testcase("test1.txt", quality=1),
        cm.create_testcase("test2.txt", quality=9),
        cm.create_testcase("test3.txt", quality=2),
        cm.create_testcase("test4.txt", quality=3),
    ]
    tools = ["tool2", "tool2", "tool1", "tool1"]
    for i in range(4):
        cm.create_report(
            shortSignature="report #%d" % (i + 1),
            client="client #%d" % (i + 1),
            os="os #%d" % (i + 1),
            product="product #%d" % (i + 1),
            product_version="%d" % (i + 1),
            platform="platform #%d" % (i + 1),
            tool=tools[i],
            testcase=tests[i],
            bucket=buckets[i],
        )
    # Create toolfilter, check that query returns only tool-filtered reports
    cm.create_toolfilter("tool1", user=user.username)
    params = {}
    if ignore_toolfilter:
        params["ignore_toolfilter"] = "1"
    if vue:
        params["vue"] = "1"
    resp = api_client.get("/reportmanager/rest/buckets/", params)
    LOG.debug(resp)
    assert resp.status_code == requests.codes["ok"]
    resp = json.loads(resp.content.decode("utf-8"))
    assert isinstance(resp, list)
    expected_buckets = 2 if ignore_toolfilter and user.username == "test" else 1
    assert len(resp) == expected_buckets
    resp = sorted(resp, key=lambda x: x["id"])
    if ignore_toolfilter and user.username == "test":
        hist = []
        if vue:
            hist = [{"begin": "ts0", "count": 3}]
        _compare_rest_result_to_bucket(resp[0], bucket1, 3, 1, hist=hist, vue=vue)
        hist = []
        if vue:
            hist = [{"begin": "ts0", "count": 1}]
        _compare_rest_result_to_bucket(resp[1], bucket2, 1, 9, hist=hist, vue=vue)
    else:
        hist = []
        if vue:
            hist = [{"begin": "ts0", "count": 2}]
        _compare_rest_result_to_bucket(resp[0], bucket1, 2, 2, hist=hist, vue=vue)


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
@pytest.mark.parametrize("ignore_toolfilter", [True, False])
def test_rest_signatures_retrieve(api_client, cm, user, ignore_toolfilter):
    """test that individual Signature can be fetched"""
    bucket1 = cm.create_bucket(shortDescription="bucket #1")
    bucket2 = cm.create_bucket(shortDescription="bucket #2")
    tests = [
        cm.create_testcase("test1.txt", quality=9),
        None,
        cm.create_testcase("test3.txt", quality=2),
        cm.create_testcase("test4.txt", quality=3),
    ]
    buckets = [bucket1, bucket1, bucket2, bucket2]
    tools = ["tool1", "tool2", "tool2", "tool3"]
    reports = [
        cm.create_report(
            shortSignature="report #%d" % (i + 1),
            client="client #%d" % (i + 1),
            os="os #%d" % (i + 1),
            product="product #%d" % (i + 1),
            product_version="%d" % (i + 1),
            platform="platform #%d" % (i + 1),
            tool=tools[i],
            testcase=tests[i],
            bucket=buckets[i],
        )
        for i in range(4)
    ]
    cm.create_toolfilter("tool1", user=user.username)
    params = {}
    if ignore_toolfilter:
        params["ignore_toolfilter"] = "1"
    for i, bucket in enumerate([bucket1, bucket2]):
        resp = api_client.get("/reportmanager/rest/buckets/%d/" % bucket.pk, params)
        LOG.debug(resp)
        allowed = (
            user.username == "test" or i == 0
        )  # only unrestricted user, or in-toolfilter
        if not allowed:
            assert resp.status_code == requests.codes["not_found"]
        else:
            status_code = resp.status_code
            resp = resp.json()
            assert status_code == requests.codes["ok"], resp["detail"]
            if user.username == "test":
                if ignore_toolfilter:
                    size, quality, best, latest = [
                        (2, 9, reports[0].id, reports[1].id),
                        (2, 2, reports[2].id, reports[3].id),
                    ][i]
                else:
                    size, quality, best, latest = [
                        (1, 9, reports[0].id, reports[0].id),
                        (0, None, None, None),
                    ][i]
            else:
                size, quality, best, latest = (1, 9, reports[0].id, reports[0].id)
            _compare_rest_result_to_bucket(resp, bucket, size, quality, best, latest)


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
@pytest.mark.parametrize("from_report", [False, True])
def test_new_signature_create(
    api_client, cm, user, from_report
):  # pylint: disable=invalid-name
    if from_report:
        if user.username == "test-restricted":
            _create_user("test")
        api_client.login(username="test", password="test")
        stderr = (
            "Program received signal SIGSEGV, Segmentation fault.\n"
            "#0  sym_a ()\n"
            "#1  sym_b ()"
        )
        report = cm.create_report(shortSignature="report #1", stderr=stderr)
        response = api_client.get(
            reverse("reportmanager:signew") + "?reportid=%d" % report.pk
        )
        LOG.debug(response)
        assert response.status_code == requests.codes["ok"]

        # create a bucket from the proposed signature and see that it matches the report
        sig = json.dumps(response.context["proposedSig"])
        desc = response.context["proposedDesc"]
        api_client.force_authenticate(user=user)
    else:
        report = cm.create_report(shortSignature="report #1", stderr="blah")
        sig = json.dumps(
            {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
        )
        desc = "bucket #1"

    resp = api_client.post(
        "/reportmanager/rest/buckets/",
        data={
            "signature": sig,
            "shortDescription": desc,
            "frequent": False,
            "permanent": False,
            "doNotReduce": False,
        },
        format="json",
    )

    LOG.debug(resp)
    bucket = Bucket.objects.get(shortDescription=desc)
    report = ReportEntry.objects.get(pk=report.pk)  # re-read
    assert report.bucket == bucket
    assert json.loads(bucket.signature) == json.loads(sig)
    assert bucket.shortDescription == desc
    assert not bucket.doNotReduce
    assert not bucket.frequent
    assert not bucket.permanent
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
@pytest.mark.parametrize("many", [False, True])
def test_new_signature_create_w_reassign(
    api_client, cm, user, many
):  # pylint: disable=invalid-name
    if many:
        reports = [
            cm.create_report(shortSignature="report #1", stderr="blah")
            for _ in range(201)
        ]
    else:
        report = cm.create_report(shortSignature="report #1", stderr="blah")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )

    resp = api_client.post(
        "/reportmanager/rest/buckets/?reassign=true",
        data={
            "signature": sig,
            "shortDescription": "bucket #1",
            "doNotReduce": False,
            "frequent": False,
            "permanent": False,
        },
        format="json",
    )

    LOG.debug(resp)
    bucket = Bucket.objects.get(shortDescription="bucket #1")
    if many:
        reports = [
            ReportEntry.objects.get(pk=report.pk) for report in reports
        ]  # re-read
        for report in reports:
            assert report.bucket == bucket
    else:
        report = ReportEntry.objects.get(pk=report.pk)  # re-read
        assert report.bucket == bucket
    assert json.loads(bucket.signature) == json.loads(sig)
    assert bucket.shortDescription == "bucket #1"
    assert not bucket.doNotReduce
    assert not bucket.frequent
    assert not bucket.permanent
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }


@pytest.mark.parametrize("user", ["normal", "restricted"], indirect=True)
@pytest.mark.parametrize("many", [False, True])
def test_new_signature_preview(
    api_client, cm, user, many
):  # pylint: disable=invalid-name
    if many:
        reports = [
            cm.create_report(shortSignature="report #1", stderr="blah")
            for _ in range(201)
        ]
    else:
        report = cm.create_report(shortSignature="report #1", stderr="blah")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )

    resp = api_client.post(
        "/reportmanager/rest/buckets/?save=false",
        data={
            "signature": sig,
            "shortDescription": "bucket #1",
            "doNotReduce": False,
            "frequent": False,
            "permanent": False,
        },
        format="json",
    )

    LOG.debug(resp)
    assert not Bucket.objects.filter(shortDescription="bucket #1").exists()
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["warningMessage"] == "This is a preview, don't forget to save!"
    in_list = data["inList"]
    out_list = data["outList"]
    assert not out_list
    if many:
        reports = [
            ReportEntry.objects.get(pk=report.pk) for report in reports
        ]  # re-read
        for report in reports:
            assert report.bucket is None

        assert len(in_list) == 100
        assert data["inListCount"] == 201

        for shown, report in zip(reversed(data["inList"]), reports[-100:]):
            assert shown["id"] == report.pk
    else:
        report = ReportEntry.objects.get(pk=report.pk)  # re-read
        assert report.bucket is None

        assert len(in_list) == 1
        assert in_list[0]["id"] == report.pk


@pytest.mark.parametrize("user", ["normal"], indirect=True)
@pytest.mark.parametrize("do_not_reduce", [True, False])
@pytest.mark.parametrize("frequent", [True, False])
@pytest.mark.parametrize("permanent", [True, False])
def test_edit_signature_edit(
    api_client,
    cm,  # pylint: disable=invalid-name
    user,
    do_not_reduce,
    frequent,
    permanent,
):
    bucket = cm.create_bucket()
    report = cm.create_report(shortSignature="report #1", stderr="blah")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )

    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?reassign=false" % bucket.pk,
        data={
            "signature": sig,
            "shortDescription": "bucket #1",
            "doNotReduce": do_not_reduce,
            "frequent": frequent,
            "permanent": permanent,
        },
        format="json",
    )

    LOG.debug(resp)
    bucket = Bucket.objects.get(pk=bucket.pk)
    report = ReportEntry.objects.get(pk=report.pk)  # re-read
    assert report.bucket is None
    assert json.loads(bucket.signature) == json.loads(sig)
    assert bucket.shortDescription == "bucket #1"
    assert bucket.doNotReduce is do_not_reduce
    assert bucket.frequent is frequent
    assert bucket.permanent is permanent
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }


@pytest.mark.parametrize("user", ["normal"], indirect=True)
@pytest.mark.parametrize("many", [False, True])
def test_edit_signature_edit_w_reassign(
    api_client, cm, user, many
):  # pylint: disable=invalid-name
    bucket = cm.create_bucket()
    if many:
        reports = [
            cm.create_report(shortSignature="report #1", stderr="blah")
            for _ in range(201)
        ]
    else:
        report = cm.create_report(shortSignature="report #1", stderr="blah")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )

    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?reassign=true" % bucket.pk,
        data={
            "signature": sig,
            "shortDescription": "bucket #1",
            "doNotReduce": False,
            "frequent": False,
            "permanent": False,
        },
        format="json",
    )

    LOG.debug(resp)
    bucket = Bucket.objects.get(pk=bucket.pk)
    if many:
        reports = [
            ReportEntry.objects.get(pk=report.pk) for report in reports
        ]  # re-read
        for report in reports:
            assert report.bucket == bucket
    else:
        report = ReportEntry.objects.get(pk=report.pk)  # re-read
        assert report.bucket == bucket
    assert json.loads(bucket.signature) == json.loads(sig)
    assert bucket.shortDescription == "bucket #1"
    assert not bucket.doNotReduce
    assert not bucket.frequent
    assert not bucket.permanent
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }


@pytest.mark.parametrize("user", ["normal"], indirect=True)
@pytest.mark.parametrize("many", [False, True])
def test_edit_signature_edit_preview(
    api_client, cm, user, many
):  # pylint: disable=invalid-name
    bucket = cm.create_bucket()
    if many:
        reports1 = [
            cm.create_report(shortSignature="report #1", stderr="foo", bucket=bucket)
            for _ in range(201)
        ]
        reports2 = [
            cm.create_report(shortSignature="report #2", stderr="blah")
            for _ in range(201)
        ]
    else:
        report1 = cm.create_report(
            shortSignature="report #1", stderr="foo", bucket=bucket
        )
        report2 = cm.create_report(shortSignature="report #2", stderr="blah")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )

    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?save=false" % bucket.pk,
        data={
            "signature": sig,
            "shortDescription": "bucket #1",
            "doNotReduce": False,
            "frequent": False,
            "permanent": False,
        },
        format="json",
    )

    LOG.debug(resp)
    bucket = Bucket.objects.get(pk=bucket.pk)  # re-read
    # Bucket wasn't updated
    assert bucket.shortDescription == ""
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["warningMessage"] == "This is a preview, don't forget to save!"
    in_list = data["inList"]
    out_list = data["outList"]
    if many:
        assert len(in_list) == 100
        assert len(out_list) == 100
        assert data["inListCount"] == 201
        assert data["outListCount"] == 201
        for report in reports1:
            report = ReportEntry.objects.get(pk=report.pk)  # re-read
            assert report.bucket == bucket
        for report in reports2:
            report = ReportEntry.objects.get(pk=report.pk)  # re-read
            assert report.bucket is None
        for shown, report in zip(reversed(in_list), reports2[-100:]):
            assert shown["id"] == report.pk
        for shown, report in zip(reversed(out_list), reports1[-100:]):
            assert shown["id"] == report.pk
    else:
        assert len(in_list) == 1
        assert len(out_list) == 1
        report1 = ReportEntry.objects.get(pk=report1.pk)  # re-read
        report2 = ReportEntry.objects.get(pk=report2.pk)  # re-read
        assert report1.bucket == bucket
        assert report2.bucket is None
        assert out_list[0]["id"] == report1.pk
        assert in_list[0]["id"] == report2.pk


def test_edit_signature_set_frequent(api_client, cm, user_normal):
    """test that partial_update action marks a signature frequent without touching
    anything else"""
    bug = cm.create_bug("123")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )
    bucket = cm.create_bucket(shortDescription="bucket #1", signature=sig, bug=bug)
    assert not bucket.frequent
    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?reassign=false" % bucket.pk,
        data={
            "frequent": True,
        },
        format="json",
    )
    LOG.debug(resp)
    assert resp.status_code == requests.codes["ok"]
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }
    bucket.refresh_from_db()
    assert bucket.frequent
    assert bucket.bug == bug


def test_edit_signature_unassign_external_bug(api_client, cm, user_normal):
    """test that partial_update action marks a signature frequent without touching
    anything else"""
    bug = cm.create_bug("123")
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )
    bucket = cm.create_bucket(shortDescription="bucket #1", signature=sig, bug=bug)
    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?reassign=false" % bucket.pk,
        data={
            "bug": None,
        },
        format="json",
    )
    LOG.debug(resp)
    assert resp.status_code == requests.codes["ok"]
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }
    bucket.refresh_from_db()
    assert bucket.bug is None


def test_edit_signature_assign_external_bug(api_client, cm, user_normal):
    """test that partial_update action create a new Bug and assign it to this Bucket"""
    provider = cm.create_bugprovider(
        hostname="test-provider.com", urlTemplate="test-provider.com/template"
    )
    sig = json.dumps(
        {"symptoms": [{"src": "stderr", "type": "output", "value": "/^blah/"}]}
    )
    bucket = cm.create_bucket(shortDescription="bucket #1", signature=sig)
    assert not Bug.objects.count()
    resp = api_client.patch(
        "/reportmanager/rest/buckets/%d/?reassign=false" % bucket.pk,
        data={
            "bug": 123456,
            "bug_provider": provider.id,
        },
        format="json",
    )
    LOG.debug(resp)
    assert resp.status_code == requests.codes["ok"]
    assert resp.json() == {
        "url": reverse("reportmanager:sigview", kwargs={"sigid": bucket.pk})
    }
    assert Bug.objects.count() == 1
    createdBug = Bug.objects.get()
    assert createdBug.externalId == "123456"
    assert createdBug.externalType == provider
    bucket.refresh_from_db()
    assert bucket.bug == createdBug
