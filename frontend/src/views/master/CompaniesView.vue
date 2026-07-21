<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon icon-gray"><TeamOutlined /></div>
            <div>
              <div class="stat-label">전체 거래처</div>
              <div class="stat-value">{{ stats.total }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div class="stat-icon icon-blue"><IdcardOutlined /></div>
            <div>
              <div class="stat-label">사업자번호 등록</div>
              <div class="stat-value" style="color:#1677ff">{{ stats.withBusinessNo }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div class="stat-icon icon-green"><BankOutlined /></div>
            <div>
              <div class="stat-label">계좌 등록</div>
              <div class="stat-value" style="color:#52c41a">{{ stats.withBank }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">거래처 관리</span></template>
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="search"
            placeholder="거래처명 / 약칭 / 사업자번호 검색"
            style="width:280px"
            allow-clear
            @search="resetAndLoad"
          />
          <input ref="excelInput" type="file" accept=".xlsx,.xlsm,.xls" style="display:none" @change="handleExcelFile" />
          <a-button :loading="importing" @click="excelInput?.click()">
            <template #icon><UploadOutlined /></template>엑셀 업로드
          </a-button>
          <a-button @click="downloadTemplate">
            <template #icon><DownloadOutlined /></template>양식 다운로드
          </a-button>
          <a-button type="primary" @click="openEditor(null)">
            <template #icon><PlusOutlined /></template>신규 등록
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="companies"
        :loading="loading"
        :pagination="tablePagination"
        row-key="id"
        size="middle"
        :scroll="{ x: 3260 }"
        @change="handleTableChange"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click="openEditor(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a-popconfirm
                title="이 거래처를 삭제하시겠습니까?"
                ok-text="삭제"
                ok-type="danger"
                cancel-text="취소"
                @confirm="handleDelete(record.id)"
              >
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal :mask-closable="false"
      v-model:open="editorOpen"
      :title="editItem ? '거래처 수정' : '거래처 신규 등록'"
      width="720px"
      wrap-class-name="company-editor-modal"
      :confirm-loading="saving"
      ok-text="저장"
      cancel-text="취소"
      @ok="handleSave"
    >
      <div class="legacy-editor">
        <div class="legacy-list">
          <div class="legacy-grid-head">
            <div class="check-cell"><CheckSquareOutlined /></div>
            <div>코드</div>
            <div>거래처명</div>
            <div>구분</div>
          </div>
          <div class="legacy-grid-body">
            <div
              v-for="company in companies"
              :key="company.id"
              :class="['legacy-grid-row', editItem?.id === company.id ? 'selected' : '']"
              @click="selectCompanyFromList(company)"
            >
              <div class="check-cell-body">
                <a-checkbox
                  :checked="editItem?.id === company.id"
                  @click.stop
                  @change="selectCompanyFromList(company)"
                />
              </div>
              <div>{{ company.company_code }}</div>
              <div>{{ company.company_name }}</div>
              <div>{{ company.company_type || '거래처' }}</div>
            </div>
          </div>
          <div class="legacy-grid-foot"></div>
        </div>

        <a-form ref="formRef" :model="form" class="legacy-form">
          <a-tabs v-model:activeKey="activeTab" type="card" size="small" :class="['legacy-tabs', `tab-${activeTab}`]">
            <a-tab-pane key="basic" tab="기본등록사항">
              <div class="section-box basic-main">
                <FormLine label="거래처약칭" name="short_name" required>
                  <a-input v-model:value="form.short_name" />
                </FormLine>
                <FormLine label="사업자등록번호" name="business_no">
                  <a-input v-model:value="form.business_no" placeholder="___-__-_____" />
                  <a-button class="lookup-wide" @click="checkBusinessStatus">국세청휴폐업조회</a-button>
                </FormLine>
                <FormLine label="주민등록번호" name="resident_no">
                  <a-select v-model:value="form.resident_type" class="select-sm">
                    <a-select-option value="내국인">내국인</a-select-option>
                    <a-select-option value="외국인">외국인</a-select-option>
                  </a-select>
                  <a-input v-model:value="form.resident_no" placeholder="______-_______" />
                </FormLine>
                <FormLine label="대표자성명" name="ceo_name">
                  <a-input v-model:value="form.ceo_name" />
                </FormLine>
                <FormLine label="업태" name="business_type">
                  <a-input v-model:value="form.business_type" />
                </FormLine>
                <FormLine label="종목" name="business_item">
                  <a-input v-model:value="form.business_item" />
                </FormLine>
                <FormLine label="우편번호" name="postal_code">
                  <a-input v-model:value="form.postal_code" class="code-input" />
                  <a-button class="icon-button" @click="openPostLookup('postal_code', 'address_detail1')"><SearchOutlined /></a-button>
                </FormLine>
                <FormLine label="사업장주소" name="address_detail1" wide>
                  <a-input v-model:value="form.address_detail1" />
                </FormLine>
                <FormLine label="" name="address_detail2" wide>
                  <a-input v-model:value="form.address_detail2" />
                </FormLine>
                <FormLine label="전화번호" name="phone">
                  <a-input v-model:value="form.phone" />
                </FormLine>
                <FormLine label="팩스번호" name="fax">
                  <a-input v-model:value="form.fax" />
                </FormLine>
                <FormLine label="홈페이지" name="homepage" wide>
                  <a-input v-model:value="form.homepage" />
                  <a-button class="icon-button" @click="openHomepage(form.homepage)"><HomeOutlined /></a-button>
                </FormLine>
                <FormLine label="메일주소" name="email" wide>
                  <a-input v-model:value="form.email" />
                  <a-button class="icon-button" @click="openMail(form.email)"><MailOutlined /></a-button>
                </FormLine>
                <FormLine label="주류코드" name="liquor_code">
                  <a-input v-model:value="form.liquor_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('liquor', 'liquor_code', 'liquor_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.liquor_name" />
                </FormLine>
                <FormLine label="국가코드" name="country_code" wide>
                  <a-select v-model:value="form.country_code">
                    <a-select-option value="">선택</a-select-option>
                    <a-select-option value="KR">KR 대한민국</a-select-option>
                    <a-select-option value="DE">DE 독일</a-select-option>
                    <a-select-option value="US">US 미국</a-select-option>
                    <a-select-option value="CN">CN 중국</a-select-option>
                  </a-select>
                </FormLine>
              </div>

              <div class="section-box basic-extra">
                <FormLine label="프로젝트" name="project_code">
                  <a-input v-model:value="form.project_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('project', 'project_code', 'project_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.project_name" />
                </FormLine>
                <FormLine label="거래처분류" name="company_category_code">
                  <a-input v-model:value="form.company_category_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('companyCategory', 'company_category_code', 'company_category_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.company_category_name" />
                </FormLine>
                <FormLine label="거래처등급" name="company_grade_code">
                  <a-input v-model:value="form.company_grade_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('companyGrade', 'company_grade_code', 'company_grade_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.company_grade_name" />
                </FormLine>
                <FormLine label="수금거래처" name="collection_customer_code">
                  <a-input v-model:value="form.collection_customer_code" class="code-input" />
                  <a-button class="icon-button" @click="openCompanyLookup('collection_customer_code', 'collection_customer_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.collection_customer_name" />
                </FormLine>
                <FormLine label="지역" name="region_code">
                  <a-input v-model:value="form.region_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('region', 'region_code', 'region_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.region_name" />
                </FormLine>
                <FormLine label="외부데이터코드" name="external_data_code" wide>
                  <a-input v-model:value="form.external_data_code" />
                </FormLine>
                <FormLine label="전자세금계산서 여부" name="electronic_tax_invoice_yn">
                  <a-select v-model:value="form.electronic_tax_invoice_yn" class="select-sm">
                    <a-select-option value="">선택</a-select-option>
                    <a-select-option value="Y">Y</a-select-option>
                    <a-select-option value="N">N</a-select-option>
                  </a-select>
                </FormLine>
                <FormLine label="단위신고거래처" name="single_report_customer_code">
                  <a-input v-model:value="form.single_report_customer_code" class="code-input" />
                  <a-button class="icon-button" @click="openCompanyLookup('single_report_customer_code', 'single_report_customer_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.single_report_customer_name" />
                  <span class="inline-label">종사업장번호</span>
                  <a-input v-model:value="form.tax_business_no" class="code-input" />
                </FormLine>
                <FormLine label="조달청 다수공급자" name="multi_supplier_yn">
                  <a-select v-model:value="form.multi_supplier_yn" class="select-sm">
                    <a-select-option value="">선택</a-select-option>
                    <a-select-option value="Y">Y</a-select-option>
                    <a-select-option value="N">N</a-select-option>
                  </a-select>
                </FormLine>
                <FormLine label="용도구분" name="purpose_type" wide>
                  <a-select v-model:value="form.purpose_type">
                    <a-select-option value="">선택</a-select-option>
                    <a-select-option value="매출">매출</a-select-option>
                    <a-select-option value="매입">매입</a-select-option>
                    <a-select-option value="공통">공통</a-select-option>
                  </a-select>
                </FormLine>
              </div>

              <div class="section-box basic-bottom">
                <FormLine label="거래시작일" name="transaction_start_date">
                  <a-date-picker v-model:value="form.transaction_start_date" value-format="YYYY-MM-DD" />
                </FormLine>
                <FormLine label="사용여부" name="use_yn">
                  <a-select v-model:value="form.use_yn" class="select-sm">
                    <a-select-option value="Y">1. 사용</a-select-option>
                    <a-select-option value="N">0. 미사용</a-select-option>
                  </a-select>
                </FormLine>
              </div>
            </a-tab-pane>

            <a-tab-pane key="trade" tab="거래등록사항">
              <div class="section-box trade-section">
                <div class="section-title"><CaretRightOutlined />계약정보</div>
                <FormLine label="거래기간" name="contract_start_date">
                  <a-date-picker v-model:value="form.contract_start_date" value-format="YYYY-MM-DD" />
                  <span class="dash">~</span>
                  <a-date-picker v-model:value="form.contract_end_date" value-format="YYYY-MM-DD" />
                </FormLine>
                <FormLine label="거래상태" name="transaction_status">
                  <a-select v-model:value="form.transaction_status" class="select-md">
                    <a-select-option value="">선택</a-select-option>
                    <a-select-option value="active">거래중</a-select-option>
                    <a-select-option value="hold">보류</a-select-option>
                    <a-select-option value="closed">종료</a-select-option>
                  </a-select>
                  <span class="inline-label">할인율</span>
                  <a-input-number v-model:value="form.discount_rate" :min="0" :max="100" class="number-input" />
                </FormLine>
                <FormLine label="계약금액" name="contract_amount">
                  <a-input-number v-model:value="form.contract_amount" :min="0" class="amount-input" />
                </FormLine>
                <FormLine label="활용여비" name="use_expense_amount">
                  <a-input-number v-model:value="form.use_expense_amount" :min="0" class="amount-input" />
                </FormLine>
                <FormLine label="결제조건" name="payment_terms">
                  <a-input v-model:value="form.payment_terms" />
                </FormLine>
                <FormLine label="여신한도액" name="credit_limit">
                  <a-input-number v-model:value="form.credit_limit" :min="0" class="amount-input" />
                </FormLine>
                <FormLine label="한도회기일" name="limit_recovery_days">
                  <a-input-number v-model:value="form.limit_recovery_days" :min="0" class="amount-input" />
                </FormLine>
              </div>

              <div class="section-box trade-section payment-section">
                <div class="section-title"><CaretRightOutlined />매입(지급)거래처 관리</div>
                <FormLine label="금융기관" name="payment_bank_code">
                  <a-input v-model:value="form.payment_bank_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('bank', 'payment_bank_code', 'payment_bank_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.payment_bank_name" />
                </FormLine>
                <FormLine label="지점명" name="payment_branch_name">
                  <a-input v-model:value="form.payment_branch_name" />
                </FormLine>
                <FormLine label="계좌번호" name="payment_account_no">
                  <a-input v-model:value="form.payment_account_no" />
                </FormLine>
                <FormLine label="예금주" name="payment_account_holder">
                  <a-input v-model:value="form.payment_account_holder" />
                </FormLine>
                <FormLine label="전표유형" name="slip_type_code">
                  <a-input v-model:value="form.slip_type_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('slipType', 'slip_type_code', 'slip_type_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.slip_type_name" />
                </FormLine>
                <FormLine label="세무구분" name="tax_category_code">
                  <a-input v-model:value="form.tax_category_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('taxCategory', 'tax_category_code', 'tax_category_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.tax_category_name" />
                </FormLine>
                <FormLine label="지급예정(매월)" name="payment_due_day">
                  <a-input-number v-model:value="form.payment_due_day" :min="1" :max="31" class="day-input" />
                  <span class="inline-suffix">일</span>
                </FormLine>
              </div>
            </a-tab-pane>

            <a-tab-pane key="extra" tab="추가등록사항">
              <div class="section-box extra-section">
                <div class="section-title"><CaretRightOutlined />관리 담당자</div>
                <FormLine label="부서명" name="manager_department_code">
                  <a-input v-model:value="form.manager_department_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('department', 'manager_department_code', 'manager_department_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.manager_department_name" />
                </FormLine>
                <FormLine label="직급" name="manager_position">
                  <a-input v-model:value="form.manager_position" />
                </FormLine>
                <FormLine label="담당업무" name="manager_task">
                  <a-input v-model:value="form.manager_task" />
                </FormLine>
                <FormLine label="담당사원" name="manager_employee_code">
                  <a-input v-model:value="form.manager_employee_code" class="code-input" />
                  <a-button class="icon-button" @click="openLookup('employee', 'manager_employee_code', 'manager_employee_name')"><SearchOutlined /></a-button>
                  <a-input v-model:value="form.manager_employee_name" />
                </FormLine>
                <FormLine label="전화번호" name="manager_phone">
                  <a-input v-model:value="form.manager_phone" />
                  <span class="inline-label">내선</span>
                  <a-input v-model:value="form.manager_extension" class="code-input" />
                </FormLine>
                <FormLine label="Mobile" name="manager_mobile">
                  <a-input v-model:value="form.manager_mobile" />
                </FormLine>
                <FormLine label="메일주소" name="manager_email" wide>
                  <a-input v-model:value="form.manager_email" />
                  <a-button class="icon-button" @click="openMail(form.manager_email)"><MailOutlined /></a-button>
                </FormLine>
              </div>

              <div class="section-box extra-section receive-section">
                <div class="section-title"><CaretRightOutlined />수신처 관리</div>
                <FormLine label="우편번호" name="receiver_postal_code">
                  <a-input v-model:value="form.receiver_postal_code" class="code-input" />
                  <a-button class="icon-button" @click="openPostLookup('receiver_postal_code', 'receiver_address1')"><SearchOutlined /></a-button>
                </FormLine>
                <FormLine label="수신처주소" name="receiver_address1" wide>
                  <a-input v-model:value="form.receiver_address1" />
                </FormLine>
                <FormLine label="" name="receiver_address2" wide>
                  <a-input v-model:value="form.receiver_address2" />
                </FormLine>
                <FormLine label="전화번호" name="receiver_phone">
                  <a-input v-model:value="form.receiver_phone" />
                </FormLine>
                <FormLine label="팩스번호" name="receiver_fax">
                  <a-input v-model:value="form.receiver_fax" />
                </FormLine>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-form>
      </div>
    </a-modal>

    <a-modal :mask-closable="false"
      v-model:open="lookupOpen"
      :title="lookupTitle"
      width="520px"
      :footer="null"
    >
      <a-input-search
        v-if="lookupConfig.type === 'post'"
        v-model:value="lookupSearch"
        placeholder="도로명, 건물명, 지번을 입력하세요"
        enter-button="검색"
        allow-clear
        style="margin-bottom:8px"
        @search="searchPostalAddresses"
      />
      <a-table
        :columns="lookupColumns"
        :data-source="lookupRows"
        :loading="lookupLoading"
        :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
        row-key="code"
        size="small"
        :custom-row="record => ({ onDblclick: () => selectLookup(record) })"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-button type="link" size="small" @click="selectLookup(record)">선택</a-button>
          </template>
        </template>
      </a-table>
    </a-modal>

    <a-modal :mask-closable="false"
      v-model:open="businessStatusModal.open"
      title="국세청 휴폐업 조회 결과"
      ok-text="확인"
      :cancel-button-props="{ style: { display: 'none' } }"
      @ok="businessStatusModal.open = false"
    >
      <a-descriptions bordered size="small" :column="1">
        <a-descriptions-item label="사업자등록번호">{{ businessStatusModal.result.business_no || '-' }}</a-descriptions-item>
        <a-descriptions-item label="사업자 상태">
          <a-tag :color="businessStatusColor">{{ businessStatusModal.result.business_status || '상태 미확인' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="상태 코드">{{ businessStatusModal.result.business_status_code || '-' }}</a-descriptions-item>
        <a-descriptions-item label="과세 유형">{{ businessStatusModal.result.tax_type || '-' }}</a-descriptions-item>
        <a-descriptions-item label="과세 유형 코드">{{ businessStatusModal.result.tax_type_code || '-' }}</a-descriptions-item>
        <a-descriptions-item label="폐업일자">{{ businessStatusModal.result.closed_date || '-' }}</a-descriptions-item>
      </a-descriptions>
    </a-modal>

    <a-modal :mask-closable="false"
      v-model:open="apiKeyModal.open"
      title="외부 API 인증키 확인"
      ok-text="인증키 저장"
      cancel-text="닫기"
      :confirm-loading="apiKeyModal.saving"
      :ok-button-props="{ disabled: !authStore.isAdmin }"
      @ok="saveExternalApiKey"
    >
      <a-alert
        type="warning"
        show-icon
        :message="apiKeyModal.message"
        style="margin-bottom:12px"
      />
      <template v-if="authStore.isAdmin">
        <a-form layout="vertical">
          <a-form-item :label="apiKeyModal.service === 'postal' ? '우체국 우편번호 인증키' : '국세청 휴폐업조회 인증키'">
            <a-input-password
              v-model:value="apiKeyModal.key"
              placeholder="새 인증키를 입력하세요"
              allow-clear
            />
          </a-form-item>
        </a-form>
      </template>
      <a-alert
        v-else
        type="info"
        show-icon
        message="관리자 권한 계정으로 로그인하면 이 팝업에서 인증키를 갱신할 수 있습니다."
      />
    </a-modal>
  </div>
</template>

<script setup>
import { defineComponent, h, ref, reactive, computed, onMounted, resolveComponent } from 'vue'
import { message } from 'ant-design-vue'
import { masterApi } from '@/api'
import { useAuthStore } from '@/store/auth'
import {
  BankOutlined,
  CaretRightOutlined,
  CheckSquareOutlined,
  DownloadOutlined,
  HomeOutlined,
  IdcardOutlined,
  MailOutlined,
  PlusOutlined,
  SearchOutlined,
  TeamOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'

const authStore = useAuthStore()

const FormLine = defineComponent({
  name: 'FormLine',
  props: {
    label: { type: String, default: '' },
    name: { type: String, required: true },
    required: { type: Boolean, default: false },
    wide: { type: Boolean, default: false },
  },
  setup(props, { slots }) {
    const AFormItem = resolveComponent('a-form-item')
    return () => h('div', { class: ['form-line', props.wide ? 'wide' : ''] }, [
      h('label', { class: 'field-label' }, props.label),
      h(
        AFormItem,
        {
          name: props.name,
          rules: props.required ? [{ required: true, message: `${props.label}을 입력하세요.` }] : [],
        },
        slots.default?.(),
      ),
    ])
  },
})

const companies = ref([])
const statsData = ref({ total: 0, withBusinessNo: 0, withBank: 0 })
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const editorOpen = ref(false)
const lookupOpen = ref(false)
const editItem = ref(null)
const activeTab = ref('basic')
const search = ref('')
const formRef = ref()
const excelInput = ref()
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const lookupConfig = ref({ type: '', codeField: '', nameField: '' })
const lookupRows = ref([])
const lookupLoading = ref(false)
const lookupSearch = ref('')
const apiKeyModal = reactive({
  open: false,
  service: '',
  message: '',
  key: '',
  saving: false,
})
const businessStatusModal = reactive({
  open: false,
  result: {},
})

const emptyForm = {
  company_group_code: '',
  company_code: '',
  short_name: '',
  company_name: '',
  company_type: 'both',
  business_no: '',
  resident_type: '내국인',
  resident_no: '',
  ceo_name: '',
  business_type: '',
  business_item: '',
  postal_code: '',
  address_detail1: '',
  address_detail2: '',
  phone: '',
  fax: '',
  homepage: '',
  email: '',
  liquor_code: '',
  liquor_name: '',
  country_code: '',
  project_code: '',
  project_name: '',
  company_category_code: '',
  company_category_name: '',
  company_grade_code: '',
  company_grade_name: '',
  collection_customer_code: '',
  collection_customer_name: '',
  region_code: '',
  region_name: '',
  external_data_code: '',
  electronic_tax_invoice_yn: '',
  single_report_customer_code: '',
  single_report_customer_name: '',
  tax_business_no: '',
  multi_supplier_yn: '',
  purpose_type: '',
  transaction_start_date: '',
  use_yn: 'Y',
  contract_start_date: '',
  contract_end_date: '',
  transaction_status: '',
  discount_rate: null,
  contract_amount: null,
  use_expense_amount: null,
  payment_terms: '',
  credit_limit: null,
  limit_recovery_days: null,
  payment_bank_code: '',
  payment_bank_name: '',
  payment_branch_name: '',
  payment_account_no: '',
  payment_account_holder: '',
  slip_type_code: '',
  slip_type_name: '',
  tax_category_code: '',
  tax_category_name: '',
  payment_due_day: null,
  manager_department_code: '',
  manager_department_name: '',
  manager_position: '',
  manager_task: '',
  manager_employee_code: '',
  manager_employee_name: '',
  manager_phone: '',
  manager_extension: '',
  manager_mobile: '',
  manager_email: '',
  manager_notes: '',
  receiver_postal_code: '',
  receiver_address1: '',
  receiver_address2: '',
  receiver_phone: '',
  receiver_fax: '',
  receiver_notes: '',
  bank_name: '',
  bank_account: '',
  bank_holder: '',
  receivables_note: '',
}

const form = reactive({ ...emptyForm })

const stats = computed(() => ({
  total: statsData.value.total,
  withBusinessNo: statsData.value.withBusinessNo,
  withBank: statsData.value.withBank,
}))

const tablePagination = computed(() => ({
  current: pagination.current,
  pageSize: pagination.pageSize,
  total: pagination.total,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: total => `총 ${total.toLocaleString()}건`,
}))

const columns = [
  { title: '회사코드', dataIndex: 'company_group_code', width: 110, align: 'center' },
  { title: '거래처코드', dataIndex: 'company_code', width: 130, align: 'center' },
  { title: '거래처 구분', dataIndex: 'company_type', width: 120, align: 'center' },
  { title: '거래처명', dataIndex: 'company_name', width: 300, align: 'center', ellipsis: true },
  { title: '거래처명 약칭', dataIndex: 'short_name', width: 240, align: 'center', ellipsis: true },
  { title: '사업자등록번호', dataIndex: 'business_no', width: 170, align: 'center' },
  { title: '대표자명', dataIndex: 'ceo_name', width: 140, align: 'center' },
  { title: '업태', dataIndex: 'business_type', width: 180, align: 'center', ellipsis: true },
  { title: '종목', dataIndex: 'business_item', width: 180, align: 'center', ellipsis: true },
  { title: '주소 상세1', dataIndex: 'address_detail1', width: 360, align: 'center', ellipsis: true },
  { title: '전화번호', dataIndex: 'phone', width: 170, align: 'center' },
  { title: '팩스번호', dataIndex: 'fax', width: 170, align: 'center' },
  { title: '이메일', dataIndex: 'email', width: 260, align: 'center', ellipsis: true },
  { title: '금융기관코드', dataIndex: 'payment_bank_code', width: 150, align: 'center' },
  { title: '금융기관', dataIndex: 'bank_name', width: 180, align: 'center', ellipsis: true },
  { title: '예금 계좌번호', dataIndex: 'bank_account', width: 220, align: 'center' },
  { title: '예금주', dataIndex: 'bank_holder', width: 220, align: 'center' },
  { title: '관리', key: 'action', width: 100, align: 'center', fixed: 'right' },
]

const staticLookups = {
  liquor: [
    { code: '01', name: '일반' },
    { code: '02', name: '주류' },
  ],
  project: [
    { code: 'P001', name: '공통 프로젝트' },
    { code: 'P002', name: '영업 프로젝트' },
  ],
  companyCategory: [
    { code: 'C01', name: '특수관계자' },
    { code: 'C02', name: '대리점' },
    { code: 'C03', name: '일반' },
  ],
  companyGrade: [
    { code: 'A', name: '우수' },
    { code: 'B', name: '일반' },
    { code: 'C', name: '주의' },
  ],
  region: [
    { code: 'SEOUL', name: '서울' },
    { code: 'GYEONGGI', name: '경기' },
    { code: 'LOCAL', name: '기타' },
  ],
  bank: [
    { code: '004', name: '국민은행' },
    { code: '020', name: '우리은행' },
    { code: '088', name: '신한은행' },
    { code: '081', name: '하나은행' },
  ],
  slipType: [
    { code: 'AP', name: '매입전표' },
    { code: 'AR', name: '매출전표' },
  ],
  taxCategory: [
    { code: 'TAX', name: '과세' },
    { code: 'FREE', name: '면세' },
  ],
  department: [
    { code: 'SALES', name: '영업팀' },
    { code: 'TECH', name: '기술팀' },
    { code: 'MGMT', name: '관리팀' },
  ],
  employee: [
    { code: 'EMP001', name: '담당자1' },
    { code: 'EMP002', name: '담당자2' },
  ],
}

const lookupColumns = [
  { title: '코드', dataIndex: 'code', width: 130, align: 'center' },
  { title: '명칭', dataIndex: 'name', width: 280, align: 'center', ellipsis: true },
  { title: '선택', key: 'action', width: 80, align: 'center' },
]

const lookupTitle = computed(() => {
  const titles = {
    company: '거래처 조회',
    post: '우편번호 조회',
    liquor: '주류코드 조회',
    project: '프로젝트 조회',
    companyCategory: '거래처분류 조회',
    companyGrade: '거래처등급 조회',
    region: '지역 조회',
    bank: '금융기관 조회',
    slipType: '전표유형 조회',
    taxCategory: '세무구분 조회',
    department: '부서 조회',
    employee: '사원 조회',
  }
  return titles[lookupConfig.value.type] || '조회'
})

const businessStatusColor = computed(() => {
  const status = businessStatusModal.result.business_status || ''
  if (status.includes('계속')) return 'green'
  if (status.includes('휴업')) return 'orange'
  if (status.includes('폐업')) return 'red'
  return 'default'
})

async function load() {
  loading.value = true
  try {
    const res = await masterApi.getCompanies({
      search: search.value || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    companies.value = res.data.items || res.data
    pagination.total = res.data.total ?? companies.value.length
    statsData.value = res.data.stats || {
      total: companies.value.length,
      withBusinessNo: companies.value.filter(c => c.business_no).length,
      withBank: companies.value.filter(c => c.bank_name || c.bank_account || c.payment_bank_name).length,
    }
  } finally {
    loading.value = false
  }
}

function resetAndLoad() {
  pagination.current = 1
  load()
}

function handleTableChange(nextPagination) {
  pagination.current = nextPagination.current || 1
  pagination.pageSize = nextPagination.pageSize || 20
  load()
}

function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

async function downloadTemplate() {
  const res = await masterApi.downloadCompaniesTemplate()
  saveBlob(res.data, '거래처_관리_양식.xlsx')
}

async function handleExcelFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await masterApi.importCompaniesExcel(formData)
    const { imported = 0, updated = 0, skipped = 0 } = res.data || {}
    message.success(`엑셀 업로드 완료: 신규 ${imported}건, 수정 ${updated}건, 제외 ${skipped}건`)
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '엑셀 업로드 중 오류가 발생했습니다.')
  } finally {
    importing.value = false
  }
}

async function openEditor(item) {
  editItem.value = item
  activeTab.value = 'basic'
  let detail = item
  if (item?.id) {
    const res = await masterApi.getCompany(item.id)
    detail = res.data
  }
  Object.assign(form, emptyForm, detail || {})
  if (form.payment_bank_name && !form.bank_name) form.bank_name = form.payment_bank_name
  if (form.payment_account_no && !form.bank_account) form.bank_account = form.payment_account_no
  if (form.payment_account_holder && !form.bank_holder) form.bank_holder = form.payment_account_holder
  editorOpen.value = true
}

async function selectCompanyFromList(company) {
  await openEditor(company)
}

function openLookup(type, codeField, nameField) {
  lookupConfig.value = { type, codeField, nameField }
  lookupSearch.value = ''
  lookupRows.value = []
  if (type === 'company') {
    lookupRows.value = companies.value.map(company => ({
      code: company.company_code,
      name: company.company_name || company.short_name,
    }))
  } else if (type !== 'post') {
    lookupRows.value = staticLookups[type] || []
  } else {
    lookupSearch.value = form[nameField] || form[codeField] || ''
  }
  lookupOpen.value = true
}

function openCompanyLookup(codeField, nameField) {
  openLookup('company', codeField, nameField)
}

function openPostLookup(codeField, nameField) {
  openLookup('post', codeField, nameField)
}

function selectLookup(record) {
  const { type, codeField, nameField } = lookupConfig.value
  if (codeField) form[codeField] = record.code
  if (nameField) form[nameField] = record.name
  if (type === 'post' && nameField) {
    message.success('우편번호와 주소를 입력했습니다.')
  }
  lookupOpen.value = false
}

function openExternalApiKeyModal(service, text) {
  apiKeyModal.service = service
  apiKeyModal.message = text || '외부 API 인증키가 만료되었거나 유효하지 않습니다.'
  apiKeyModal.key = ''
  apiKeyModal.open = true
}

function handleExternalApiError(err, fallbackService) {
  const detail = err.response?.data?.detail
  if (detail?.code !== 'external_key_invalid') return false
  openExternalApiKeyModal(detail.service || fallbackService, detail.message)
  return true
}

async function saveExternalApiKey() {
  if (!authStore.isAdmin) return
  if (!apiKeyModal.key.trim()) {
    message.warning('인증키를 입력하세요.')
    return
  }

  apiKeyModal.saving = true
  try {
    await masterApi.updateExternalApiKey({
      service: apiKeyModal.service,
      key: apiKeyModal.key.trim(),
    })
    apiKeyModal.open = false
    message.success('인증키를 갱신했습니다. 다시 조회해 주세요.')
  } catch (err) {
    message.error(err.response?.data?.detail || '인증키 저장 중 오류가 발생했습니다.')
  } finally {
    apiKeyModal.saving = false
  }
}

async function searchPostalAddresses(value) {
  const query = (typeof value === 'string' ? value : lookupSearch.value).trim()
  if (query.length < 2) {
    message.warning('검색어를 2자 이상 입력하세요.')
    return
  }

  lookupLoading.value = true
  try {
    const res = await masterApi.searchPostalAddresses(query)
    lookupRows.value = (res.data.items || []).map(item => ({
      code: item.zip_no,
      name: item.address,
      detail: item.address_detail,
    }))
    if (!lookupRows.value.length) message.info('조회 결과가 없습니다.')
  } catch (err) {
    if (!handleExternalApiError(err, 'postal')) {
      message.error(err.response?.data?.detail || '우편번호 조회 중 오류가 발생했습니다.')
    }
  } finally {
    lookupLoading.value = false
  }
}

function openHomepage(url) {
  if (!url) {
    message.warning('홈페이지 주소를 입력하세요.')
    return
  }
  const target = /^https?:\/\//i.test(url) ? url : `https://${url}`
  window.open(target, '_blank', 'noopener,noreferrer')
}

function openMail(email) {
  if (!email) {
    message.warning('메일주소를 입력하세요.')
    return
  }
  window.location.href = `mailto:${email}`
}

async function checkBusinessStatus() {
  if (!form.business_no) {
    message.warning('사업자등록번호를 입력하세요.')
    return
  }
  try {
    const res = await masterApi.getBusinessStatus(form.business_no)
    businessStatusModal.result = res.data
    businessStatusModal.open = true
  } catch (err) {
    if (!handleExternalApiError(err, 'nts')) {
      message.error(err.response?.data?.detail || '국세청 휴폐업 조회 중 오류가 발생했습니다.')
    }
  }
}

function normalizePayload() {
  const payload = {
    ...form,
    company_name: form.company_name || form.short_name,
    address: [form.address_detail1, form.address_detail2].filter(Boolean).join(' '),
    bank_name: form.bank_name || form.payment_bank_name,
    bank_account: form.bank_account || form.payment_account_no,
    bank_holder: form.bank_holder || form.payment_account_holder,
  }
  ;[
    'transaction_start_date',
    'contract_start_date',
    'contract_end_date',
    'discount_rate',
    'contract_amount',
    'use_expense_amount',
    'credit_limit',
    'limit_recovery_days',
    'payment_due_day',
  ].forEach((key) => {
    if (payload[key] === '') payload[key] = null
  })
  return payload
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = normalizePayload()
    if (editItem.value) {
      await masterApi.updateCompany(editItem.value.id, payload)
      message.success('수정되었습니다.')
    } else {
      await masterApi.createCompany(payload)
      message.success('등록되었습니다.')
    }
    editorOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await masterApi.deleteCompany(id)
    message.success('삭제되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-green { border-left-color: #52c41a; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-gray { background: #f0f2f5; color: #595959; }
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-green { background: #f6ffed; color: #52c41a; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.sub-text { color: #8c8c8c; font-size: 12px; line-height: 1.4; }
.del-link { color: #e74c3c; }
.del-link:hover { color: #c0392b; }
.legacy-editor { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 10px; height: 100%; min-height: 0; background: #f7fbff; overflow: hidden; }
.legacy-list { border: 1px solid #b9d3ef; background: #fff; display: flex; flex-direction: column; min-width: 0; }
.legacy-grid-head { display: grid; grid-template-columns: 34px 76px 1fr 46px; background: #2f76a7; color: #fff; font-weight: 700; font-size: 14px; height: 30px; line-height: 30px; text-align: center; }
.legacy-grid-head > div { border-right: 1px solid rgba(255,255,255,0.35); }
.check-cell { font-size: 16px; color: #ffcf4d; }
.check-cell-body { display: flex; align-items: center; justify-content: center; padding: 0 !important; }
.legacy-grid-body { flex: 1; overflow: auto; background: #fff; }
.legacy-grid-row { display: grid; grid-template-columns: 34px 76px 1fr 46px; min-height: 28px; border-bottom: 1px solid #e6f0fb; cursor: pointer; font-size: 12px; }
.legacy-grid-row:hover { background: #eef6ff; }
.legacy-grid-row.selected { background: #dceeff; }
.legacy-grid-row > div { padding: 5px 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-right: 1px solid #eef2f7; }
.legacy-grid-foot { height: 26px; border-top: 1px solid #f4c06d; background: linear-gradient(90deg, #fff0c4 0 36px, #f38b00 36px 140px, #fff0c4 140px); }
.legacy-form { min-width: 0; min-height: 0; overflow: hidden; }
.legacy-tabs { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.section-box { border: 1px solid #8fbbe8; border-radius: 4px; background: #eaf4fb; padding: 10px 14px; margin-bottom: 7px; }
.basic-main { min-height: 379px; }
.basic-extra { min-height: 286px; }
.basic-bottom { min-height: 86px; }
.trade-section { min-height: 238px; }
.payment-section { min-height: 238px; }
.extra-section { min-height: 300px; }
.receive-section { min-height: 260px; }
.section-title { display: flex; align-items: center; gap: 4px; color: #113d5e; font-weight: 700; margin-bottom: 9px; }
.form-line { display: grid; grid-template-columns: 135px minmax(0, 1fr); align-items: center; min-height: 34px; }
.field-label { text-align: right; padding-right: 10px; font-size: 14px; color: #111; white-space: nowrap; }
.inline-label { white-space: nowrap; margin-left: 8px; font-size: 13px; color: #111; align-self: center; }
.inline-suffix, .dash { align-self: center; font-size: 13px; color: #111; }
.code-input { max-width: 95px; }
.select-sm { max-width: 125px; }
.select-md { max-width: 170px; }
.amount-input { width: 260px; }
.number-input { width: 90px; }
.day-input { width: 90px; }
.lookup-wide { width: 150px; color: #fff; background: #aeb5bb; border-color: #9da5ad; }
.icon-button { width: 24px; padding: 0; flex: 0 0 24px; color: #557ca5; }
:deep(.legacy-tabs > .ant-tabs-nav) { flex: 0 0 auto; margin: 0; }
:deep(.legacy-tabs .ant-tabs-tab) { min-width: 126px; justify-content: center; border-color: #8aa9cf !important; background: linear-gradient(#f7f7f7, #d7d7d7) !important; font-weight: 700; }
:deep(.legacy-tabs .ant-tabs-tab-btn) { overflow: visible; text-overflow: clip; white-space: nowrap; }
:deep(.legacy-tabs .ant-tabs-tab-active) { background: #eaf4fb !important; border-bottom-color: #eaf4fb !important; }
:deep(.legacy-tabs .ant-tabs-content-holder) { flex: 1 1 auto; border: 1px solid #8fbbe8; border-top: none; padding: 0; background: #eaf4fb; height: auto; overflow: hidden; min-height: 0; }
:deep(.legacy-tabs .ant-tabs-content) { height: 100%; }
:deep(.legacy-tabs .ant-tabs-tabpane) { height: 100%; padding: 0 0 18px; overflow: auto; box-sizing: border-box; }
:deep(.form-line .ant-form-item) { margin: 0; min-width: 0; }
:deep(.form-line .ant-form-item-control-input) { min-height: 28px; }
:deep(.form-line .ant-form-item-control-input-content) { display: flex; align-items: center; gap: 5px; min-width: 0; }
:deep(.form-line .ant-input),
:deep(.form-line .ant-select-selector),
:deep(.form-line .ant-picker),
:deep(.form-line .ant-input-number) { border-color: #8fb3dc !important; border-radius: 0 !important; height: 28px; background: #f8f8f8; }
:deep(.wide .ant-form-item-control-input-content > .ant-input),
:deep(.wide .ant-form-item-control-input-content > .ant-select) { max-width: 535px; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-table-thead > tr > th),
:deep(.ant-table-tbody > tr > td) {
  white-space: nowrap;
}
:deep(.ant-table-tbody > tr > td) {
  height: 44px;
  padding-top: 8px;
  padding-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
}
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
