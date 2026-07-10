from fastapi import APIRouter, Query
from app.config import settings
import httpx

router = APIRouter()

@router.get("/api/holiday")
async def get_holiday(year: str = Query(..., description="조회하고자 하는 연도 (YYYY)")):
    service_key = settings.DATE_SERVIECE_KEY
    
    if not service_key:
        print("경고: LSS ERP 시스템에 DATE_SERVIECE_KEY 환경 변수가 설정되어 있지 않습니다.")
        return []
        
    url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getHoliDeInfo"
    
    params = {
        "solYear": year,
        "numOfRows": "100",
        "_type": "json",
        "ServiceKey": service_key
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=5.0)
            
            if response.status_code != 200:
                return []
                
            res_data = response.json()
            body = res_data.get("response", {}).get("body", {})
            items = body.get("items", {}).get("item", [])
            
            if not items:
                return []
                
            if isinstance(items, dict):
                items = [items]
                
            holiday_list = []
            for item in items:
                if item.get("isHoliday") == "Y":
                    locdate = str(item.get("locdate"))
                    formatted_date = f"{locdate[0:4]}-{locdate[4:6]}-{locdate[6:8]}"
                    holiday_list.append(formatted_date)
            
            return holiday_list
            
        except Exception as e:
            print(f"공공데이터 API 통신 중 예외 에러 발생: {e}")
            return []