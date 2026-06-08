import json
import re
import xml.etree.ElementTree as ET
from urllib import error, parse, request

from fastapi import HTTPException

from ..config import ENV_FILE, settings


def external_key_error(service: str, message: str, status_code: int = 503):
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": "external_key_invalid",
            "service": service,
            "message": message,
        },
    )


def _is_external_key_error(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in [
        "service_key",
        "servicekey",
        "인증키",
        "등록되지 않은",
        "expired",
        "unauthorized",
        "forbidden",
        "invalid",
        "not registered",
        "not authorized",
    ])


def _http_json(req: request.Request, service: str = "") -> dict:
    try:
        with request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        if service and (exc.code in (401, 403) or _is_external_key_error(body)):
            service_name = "국세청 사업자등록 상태조회" if service == "nts" else "외부 API"
            external_key_error(service, f"{service_name} 인증키가 만료되었거나 유효하지 않습니다.")
        raise HTTPException(status_code=502, detail=f"External API error: {body or exc.reason}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"External API request failed: {exc}")


def _xml_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def get_business_status(business_no: str) -> dict:
    if not settings.NTS_BUSINESS_STATUS_SERVICE_KEY:
        external_key_error("nts", "국세청 사업자등록 상태조회 인증키가 설정되지 않았습니다.")

    digits = re.sub(r"\D", "", business_no)
    if len(digits) != 10:
        raise HTTPException(status_code=400, detail="사업자등록번호는 숫자 10자리여야 합니다.")

    url = f"{settings.NTS_BUSINESS_STATUS_URL}?{parse.urlencode({'serviceKey': settings.NTS_BUSINESS_STATUS_SERVICE_KEY}, safe='%')}"
    payload = json.dumps({"b_no": [digits]}).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    result = _http_json(req, "nts")
    if _is_external_key_error(json.dumps(result, ensure_ascii=False)):
        external_key_error("nts", "국세청 사업자등록 상태조회 인증키가 만료되었거나 유효하지 않습니다.")

    item = (result.get("data") or [{}])[0]
    return {
        "business_no": item.get("b_no") or digits,
        "business_status": item.get("b_stt") or "",
        "business_status_code": item.get("b_stt_cd") or "",
        "tax_type": item.get("tax_type") or "",
        "tax_type_code": item.get("tax_type_cd") or "",
        "closed_date": item.get("end_dt") or "",
        "raw": item,
    }


def search_postal_addresses(query: str, current_page: int = 1, count_per_page: int = 20) -> dict:
    if not settings.POSTAL_SERVICE_KEY:
        external_key_error("postal", "우체국 우편번호 조회 인증키가 설정되지 않았습니다.")

    params = {
        "serviceKey": settings.POSTAL_SERVICE_KEY,
        "srchwrd": query,
        "currentPage": current_page,
        "countPerPage": count_per_page,
    }
    url = f"{settings.POSTAL_API_URL}?{parse.urlencode(params, safe='%')}"
    try:
        with request.urlopen(url, timeout=10) as res:
            xml_text = res.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        if exc.code in (401, 403) or _is_external_key_error(body):
            external_key_error("postal", "우체국 우편번호 조회 인증키가 만료되었거나 유효하지 않습니다.")
        raise HTTPException(status_code=502, detail=f"Postal API error: {body or exc.reason}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Postal API request failed: {exc}")

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise HTTPException(status_code=502, detail=f"Postal API XML parse failed: {exc}")

    if _is_external_key_error(xml_text):
        err_msg = root.findtext(".//errMsg") or "우체국 우편번호 조회 인증키가 만료되었거나 유효하지 않습니다."
        external_key_error("postal", f"우체국 우편번호 조회 인증키가 유효하지 않습니다. ({err_msg})")

    rows = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in {"newAddressListAreaCdSearchAll", "newAddressListAreaCd", "newAddressList", "item"}:
            continue
        zip_no = _xml_text(node, ["zipNo", "zip_no", "postNo"])
        road_address = _xml_text(node, ["lnmAdres", "rnAdres", "roadAddr", "adres", "address"])
        jibun_address = _xml_text(node, ["rnAdres", "jibunAddr"])
        if zip_no or road_address:
            rows.append({
                "zip_no": zip_no,
                "address": road_address,
                "address_detail": jibun_address if jibun_address != road_address else "",
            })

    return {"items": rows}


def update_external_api_key(service: str, key: str):
    key = key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="인증키를 입력하세요.")

    service_map = {
        "postal": "POSTAL_SERVICE_KEY",
        "nts": "NTS_BUSINESS_STATUS_SERVICE_KEY",
    }
    env_name = service_map.get(service)
    if not env_name:
        raise HTTPException(status_code=400, detail="지원하지 않는 외부 API 서비스입니다.")

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith(f"{env_name}="):
            lines[idx] = f"{env_name}={key}"
            updated = True
            break
    if not updated:
        lines.append(f"{env_name}={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    setattr(settings, env_name, key)
