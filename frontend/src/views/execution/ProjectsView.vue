<template>
  <div class="page-wrap">
    <a-tabs v-model:activeKey="activeTab" class="project-tabs">
      <a-tab-pane key="orders" tab="프로젝트리스트(수주)">
        <div class="tab-content">

    <!-- ── 통계 카드 ── -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls">
              <component :is="s.icon" />
            </div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">
                {{ s.value }}<span class="stat-unit">건</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- ── 검색 조건 ── -->
    <a-card :bordered="false" class="filter-card">
      <table class="filter-table">
        <tbody>
          <tr>
            <th>발주처</th>
            <td>
              <a-input v-model:value="filters.client_name" placeholder="발주처명" allow-clear style="width:180px" />
            </td>
            <th>계약일자</th>
            <td>
              <a-space size="small">
                <a-date-picker v-model:value="filters.contract_from" value-format="YYYY-MM-DD" placeholder="시작" style="width:130px" />
                <span>~</span>
                <a-date-picker v-model:value="filters.contract_to" value-format="YYYY-MM-DD" placeholder="종료" style="width:130px" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>PM 부서</th>
            <td>
              <a-select
                v-model:value="filters.pm_dept"
                allow-clear
                show-search
                placeholder="부서 선택"
                style="width:180px"
                :options="departmentOptions"
                option-filter-prop="label"
                option-label-prop="shortLabel"
              />
            </td>
            <th>착공일자</th>
            <td>
              <a-space size="small">
                <a-date-picker v-model:value="filters.construct_from" value-format="YYYY-MM-DD" placeholder="시작" style="width:130px" />
                <span>~</span>
                <a-date-picker v-model:value="filters.construct_to" value-format="YYYY-MM-DD" placeholder="종료" style="width:130px" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>프로젝트</th>
            <td>
              <a-input v-model:value="filters.search" placeholder="코드 또는 프로젝트명" allow-clear style="width:220px" />
            </td>
            <th>계약금액</th>
            <td>
              <a-space size="small">
                <a-input-number v-model:value="filters.amount_from" :min="0" placeholder="최소"
                  style="width:130px" :formatter="v => v ? Number(v).toLocaleString() : ''"
                  :parser="v => v.replace(/,/g, '')" />
                <span>~</span>
                <a-input-number v-model:value="filters.amount_to" :min="0" placeholder="최대"
                  style="width:130px" :formatter="v => v ? Number(v).toLocaleString() : ''"
                  :parser="v => v.replace(/,/g, '')" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>진행상태</th>
            <td>
              <a-checkbox-group v-model:value="filters.statuses">
                <a-checkbox value="미진행">미진행</a-checkbox>
                <a-checkbox value="진행중">진행중</a-checkbox>
                <a-checkbox value="완료">완료</a-checkbox>
              </a-checkbox-group>
            </td>
            <th>도급구분</th>
            <td>
              <a-space>
                <a-checkbox-group v-model:value="filters.contract_forms">
                  <a-checkbox value="원도급">원도급</a-checkbox>
                  <a-checkbox value="하도급">하도급</a-checkbox>
                  <a-checkbox value="공동도급">공동도급</a-checkbox>
                </a-checkbox-group>
                <a-divider type="vertical" />
                <a-checkbox-group v-model:value="filters.contract_types">
                  <a-checkbox value="국내">국내</a-checkbox>
                  <a-checkbox value="국외">국외</a-checkbox>
                </a-checkbox-group>
              </a-space>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="filter-footer">
        <span class="filter-count">총 <b>{{ filtered.length }}</b>건</span>
        <a-space>
          <a-button @click="resetFilters">초기화</a-button>
        </a-space>
      </div>
    </a-card>

    <!-- ── 프로젝트 목록 테이블 ── -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">프로젝트리스트(수주)</span></template>
      <template #extra>
        <a-space>
          <a-button @click="openBusinessCategoryModal">사업구분 관리</a-button>
          <input ref="excelInput" type="file" accept=".xlsx,.xlsm,.xls" style="display:none" @change="handleExcelFile" />
          <a-button :loading="importing" @click="excelInput?.click()">
            <template #icon><UploadOutlined /></template>엑셀 업로드
          </a-button>
          <a-button @click="downloadTemplate">
            <template #icon><DownloadOutlined /></template>양식 다운로드
          </a-button>
          <a-button type="primary" @click="openDrawer(null)">
            <template #icon><PlusOutlined /></template>프로젝트 등록
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="filtered"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        row-key="id"
        size="middle"
        :scroll="{ x: 3000 }"
        :row-class-name="rowClass"
        @row-click="(record) => handleRowClick(record)"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'project_name'">
            <div class="name-cell">
              <span :class="selectedId === record.id ? 'name-selected' : ''">{{ record.project_name }}</span>
              <a-tag v-if="selectedId === record.id" color="blue" style="margin-left:6px;font-size:10px">선택됨</a-tag>
            </div>
          </template>
          <template v-if="column.key === 'contract_amount'">
            <span class="num-cell">{{ record.contract_amount > 0 ? Number(record.contract_amount).toLocaleString() : '—' }}</span>
          </template>
          <template v-if="costAmountColumnKeys.includes(column.key)">
            <span class="num-cell">{{ formatAmount(projectAmountValue(record, column.key)) }}</span>
          </template>
          <template v-if="column.key === 'employment_insurance'">
            <a-tag :color="record.employment_insurance ? 'green' : 'default'">{{ record.employment_insurance ? '가입' : '미가입' }}</a-tag>
          </template>
          <template v-if="column.key === 'industrial_accident_insurance'">
            <a-tag :color="record.industrial_accident_insurance ? 'green' : 'default'">{{ record.industrial_accident_insurance ? '가입' : '미가입' }}</a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
            <a-tooltip v-if="isOverdue(record)" title="착공 종료일이 지났습니다">
              <span class="overdue-mark">⚠</span>
            </a-tooltip>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click.stop="openDrawer(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a-popconfirm :title="`'${record.project_name}' 을(를) 삭제하시겠습니까?`"
                            ok-text="삭제" ok-type="danger" cancel-text="취소"
                            @confirm="handleDelete(record.id)" @click.stop>
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
        </div>
      </a-tab-pane>

      <a-tab-pane v-if="canAccessSalesPurchaseTabs" key="sales" tab="프로젝트리스트(매출)">
        <a-card :bordered="false" class="table-card">
          <template #title><span class="card-title">프로젝트리스트(매출)</span></template>
          <template #extra>
            <a-space>
              <span class="filter-count">총 <b>{{ salesPlanRows.length }}</b>건</span>
              <a-tag v-if="salesPlanDirty" color="orange">저장 필요</a-tag>
              <a-button @click="syncSalesPlanRowsWithProjects">
                수주 프로젝트 반영
              </a-button>
              <a-button type="primary" :disabled="!salesPlanDirty" :loading="saving" @click="saveSalesPlanRows">
                저장
              </a-button>
              <a-button type="primary" @click="addSalesPlanRow">
                <template #icon><PlusOutlined /></template>행 추가
              </a-button>
            </a-space>
          </template>

          <a-table
            :columns="salesPlanColumns"
            :data-source="salesPlanRows"
            :loading="loading"
            :pagination="{ pageSize: 20, showSizeChanger: true }"
            row-key="id"
            size="small"
            :scroll="{ x: salesPlanScrollX }"
            bordered
            class="sales-plan-table"
          
        :sticky="{ offsetHeader: 56 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'job_no'">
                <a-auto-complete
                  v-model:value="record.job_no"
                  allow-clear
                  placeholder="JOB NO"
                  :options="jobNoAutoCompleteOptions"
                  option-filter-prop="value"
                  style="width:130px"
                  @select="(_, option) => applyProjectToSalesRow(record, option.projectId)"
                  @change="markSalesPlanDirty"
                />
              </template>
              <template v-else-if="column.key === 'contract_total_amount'">
                <span class="num-cell readonly-cell">{{ formatAmount(salesRowContractTotal(record)) }}</span>
              </template>
              <template v-else-if="salesPlanCalculatedKeys.has(column.key)">
                <span class="num-cell readonly-cell">{{ formatAmount(salesPlanCalculatedValue(record, column.key)) }}</span>
              </template>
              <template v-else-if="salesPlanAmountKeys.has(column.key)">
                <a-input-number
                  v-model:value="record[column.key]"
                  :min="0"
                  :formatter="amountFormatter"
                  :parser="amountParser"
                  class="table-number-input"
                  @change="markSalesPlanDirty"
                />
              </template>
              <template v-else-if="salesPlanDateKeys.has(column.key)">
                <a-date-picker
                  v-model:value="record[column.key]"
                  value-format="YYYY-MM-DD"
                  class="table-date-input"
                  @change="markSalesPlanDirty"
                />
              </template>
              <template v-else-if="column.key === 'domestic_overseas'">
                <a-select v-model:value="record.domestic_overseas" :options="domesticOverseasOptions" style="width:92px" @change="markSalesPlanDirty" />
              </template>
              <template v-else-if="column.key === 'special_relation'">
                <a-select v-model:value="record.special_relation" :options="specialRelationOptions" style="width:92px" @change="markSalesPlanDirty" />
              </template>
              <template v-else-if="column.key === 'progress_status'">
                <a-select v-model:value="record.progress_status" :options="salesProgressOptions" style="width:92px" @change="markSalesPlanDirty" />
              </template>
              <template v-else-if="salesPlanTextKeys.has(column.key)">
                <a-input v-model:value="record[column.key]" @change="markSalesPlanDirty" />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-popconfirm title="이 행을 삭제하시겠습니까?" ok-text="삭제" ok-type="danger" cancel-text="취소" @confirm="removeSalesPlanRow(record.id)">
                  <a class="del-link">삭제</a>
                </a-popconfirm>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <a-tab-pane v-if="canAccessSalesPurchaseTabs" key="purchases" tab="프로젝트리스트(매입)">
        <a-card :bordered="false" class="table-card">
          <template #title><span class="card-title">프로젝트리스트(매입)</span></template>
          <template #extra>
            <a-space>
              <span class="filter-count">총 <b>{{ purchasePlanRows.length }}</b>건</span>
              <a-tag v-if="purchasePlanDirty" color="orange">저장 필요</a-tag>
              <a-button @click="syncPurchasePlanRowsWithProjects">
                수주 프로젝트 반영
              </a-button>
              <a-button type="primary" :disabled="!purchasePlanDirty" :loading="saving" @click="savePurchasePlanRows">
                저장
              </a-button>
              <a-button type="primary" @click="addPurchasePlanRow">
                <template #icon><PlusOutlined /></template>행 추가
              </a-button>
            </a-space>
          </template>
          <a-table
            :columns="purchasePlanColumns"
            :data-source="purchasePlanRows"
            :loading="loading"
            :pagination="{ pageSize: 20, showSizeChanger: true }"
            row-key="id"
            size="small"
            :scroll="{ x: purchasePlanScrollX }"
            bordered
            class="sales-plan-table"
          
        :sticky="{ offsetHeader: 56 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'job_no'">
                <a-auto-complete
                  v-model:value="record.job_no"
                  allow-clear
                  placeholder="JOB NO"
                  :options="jobNoAutoCompleteOptions"
                  option-filter-prop="value"
                  style="width:130px"
                  @select="(_, option) => applyProjectToPurchaseRow(record, option.projectId)"
                  @change="markPurchasePlanDirty"
                />
              </template>
              <template v-else-if="purchasePlanCalculatedKeys.has(column.key)">
                <span class="num-cell readonly-cell">
                  {{ column.key === 'material_ratio' ? formatPercent(purchasePlanCalculatedValue(record, column.key)) : formatAmount(purchasePlanCalculatedValue(record, column.key)) }}
                </span>
              </template>
              <template v-else-if="purchasePlanAmountKeys.has(column.key)">
                <a-input-number
                  v-model:value="record[column.key]"
                  :min="0"
                  :formatter="amountFormatter"
                  :parser="amountParser"
                  class="table-number-input"
                  @change="markPurchasePlanDirty"
                />
              </template>
              <template v-else-if="purchasePlanDateKeys.has(column.key)">
                <a-date-picker
                  v-model:value="record[column.key]"
                  value-format="YYYY-MM-DD"
                  class="table-date-input"
                  @change="markPurchasePlanDirty"
                />
              </template>
              <template v-else-if="column.key === 'domestic_overseas'">
                <a-select v-model:value="record.domestic_overseas" :options="domesticOverseasOptions" style="width:92px" @change="markPurchasePlanDirty" />
              </template>
              <template v-else-if="column.key === 'special_relation'">
                <a-select v-model:value="record.special_relation" :options="specialRelationOptions" style="width:92px" @change="markPurchasePlanDirty" />
              </template>
              <template v-else-if="column.key === 'progress_status'">
                <a-select v-model:value="record.progress_status" :options="salesProgressOptions" style="width:92px" @change="markPurchasePlanDirty" />
              </template>
              <template v-else-if="purchasePlanTextKeys.has(column.key)">
                <a-input v-model:value="record[column.key]" @change="markPurchasePlanDirty" />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-popconfirm title="이 행을 삭제하시겠습니까?" ok-text="삭제" ok-type="danger" cancel-text="취소" @confirm="removePurchasePlanRow(record.id)">
                  <a class="del-link">삭제</a>
                </a-popconfirm>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <!-- ── 등록/수정 Drawer ── -->
    <a-modal :open="drawerOpen"
              :title="editItem ? '프로젝트 수정' : '프로젝트 등록'"
              width="840"
              wrap-class-name="project-editor-modal"
              :body-style="{ paddingBottom: '72px' }"
              :mask-closable="false"
              @cancel="closeProjectEditor"
      centered>
      <a-form :model="form" layout="vertical" ref="formRef">

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">기본 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="PJT NO." name="project_no">
              <a-input v-model:value="form.project_no" placeholder="예) PJT-2026-001" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="진행상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option value="미진행">미진행</a-select-option>
                <a-select-option value="진행중">진행중</a-select-option>
                <a-select-option value="완료">완료</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="프로젝트명" name="project_name"
              :rules="[{ required: true, message: '프로젝트명을 입력하세요.' }]">
              <a-input v-model:value="form.project_name" placeholder="프로젝트명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발주처" name="client_name"
              extra="직접 입력하거나 등록된 거래처를 검색·선택하세요.">
              <a-auto-complete
                v-model:value="form.client_name"
                :options="clientSuggestions"
                placeholder="발주처명 직접 입력 또는 검색"
                allow-clear
                @select="onClientSelect"
                @change="onClientChange"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="사업부" name="business_division">
              <a-select
                v-model:value="form.business_division"
                allow-clear
                show-search
                placeholder="사업부/실 선택"
                :options="divisionOptions"
                option-filter-prop="label"
                option-label-prop="shortLabel"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="팀" name="team_name">
              <a-select
                v-model:value="form.team_name"
                allow-clear
                show-search
                placeholder="팀/Part 선택"
                :options="teamOptions"
                option-filter-prop="label"
                option-label-prop="shortLabel"
                @change="onTeamChange"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="사업구분" name="business_category">
              <a-select v-model:value="form.business_category" allow-clear placeholder="사업구분">
                <a-select-option v-for="v in businessCategoryOptions" :key="v" :value="v">{{ v }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="SPG" name="spg">
              <a-select v-model:value="form.spg" allow-clear placeholder="SPG">
                <a-select-option v-for="v in SPG_OPTIONS" :key="v" :value="v">{{ v }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">계약 현황</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="도급형태" name="contract_form">
              <a-select v-model:value="form.contract_form">
                <a-select-option v-for="f in CONTRACT_FORMS" :key="f" :value="f">{{ f }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="국내/국외" name="contract_type">
              <a-select v-model:value="form.contract_type">
                <a-select-option value="국내">국내</a-select-option>
                <a-select-option value="국외">국외</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 시작일" name="contract_start">
              <a-date-picker v-model:value="form.contract_start" style="width:100%"
                             value-format="YYYY-MM-DD" @change="onContractStartChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 종료일" name="contract_end">
              <a-date-picker v-model:value="form.contract_end" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약금액 (원)" name="contract_amount">
              <a-input-number v-model:value="form.contract_amount" style="width:100%"
                              :min="0" :formatter="v => Number(v).toLocaleString()"
                              :parser="v => v.replace(/,/g, '')" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="도급비율 (%)" name="contract_rate">
              <a-input-number v-model:value="form.contract_rate" style="width:100%"
                              :min="0" :max="100" :step="0.01" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지역" name="region">
              <a-input v-model:value="form.region" placeholder="현장 주소지" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="구분(매출 유형)" name="revenue_type">
              <a-select v-model:value="form.revenue_type" allow-clear placeholder="매출 유형">
                <a-select-option v-for="v in REVENUE_TYPES" :key="v" :value="v">{{ v }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="공종" name="work_type">
              <a-select v-model:value="form.work_type" allow-clear>
                <a-select-option v-for="v in WORK_TYPES" :key="v" :value="v">{{ v }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="수금조건" name="collection_terms">
              <a-input v-model:value="form.collection_terms" placeholder="예) 현금 / 어음 / 계약서 발행 후 익익월말" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="하자보증기간" name="warranty_period">
              <a-input v-model:value="form.warranty_period" placeholder="예) 24개월" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="특수관계" name="special_relation">
              <a-radio-group v-model:value="form.special_relation">
                <a-radio-button value="특수관계">특수관계</a-radio-button>
                <a-radio-button value="x">x</a-radio-button>
              </a-radio-group>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="고용/산재 보험 가입 여부">
              <a-space>
                <a-checkbox v-model:checked="form.employment_insurance">고용</a-checkbox>
                <a-checkbox v-model:checked="form.industrial_accident_insurance">산재</a-checkbox>
              </a-space>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">착공 기간</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="착공 시작일" name="construct_start">
              <a-date-picker v-model:value="form.construct_start" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="착공 종료일" name="construct_end">
              <a-date-picker v-model:value="form.construct_end" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">계약금액 세부내역</span></a-divider>
        <table class="detail-cost-table">
          <thead>
            <tr>
              <th style="width:72px"></th>
              <th style="width:180px">항목</th>
              <th style="width:160px">금액 (원, 부가세 별도)</th>
              <th class="note-col">비고</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="group-cell" rowspan="3">계약금액</th>
              <td class="item-cell">자재비</td>
              <td>
                <a-input-number v-model:value="form.contract_material_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" />
              </td>
              <td class="note-cell"><a-input v-model:value="form.contract_material_note" /></td>
            </tr>
            <tr>
              <td class="item-cell">노무비</td>
              <td>
                <a-input-number v-model:value="form.contract_labor_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" />
              </td>
              <td class="note-cell"><a-input v-model:value="form.contract_labor_note" /></td>
            </tr>
            <tr class="summary-row">
              <td class="item-cell">합계</td>
              <td class="readonly-amount">{{ formatAmount(contractDetailTotal) }}</td>
              <td class="note-cell"><a-input v-model:value="form.contract_total_note" /></td>
            </tr>
          </tbody>
        </table>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">매출원가 세부내역</span></a-divider>
        <table class="detail-cost-table sales-cost-table">
          <thead>
            <tr>
              <th style="width:72px"></th>
              <th style="width:130px">구분</th>
              <th style="width:110px">세목</th>
              <th style="width:150px">금액 (원, 부가세 별도)</th>
              <th style="width:110px">계약액 대비%</th>
              <th class="note-col">비고</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="group-cell" rowspan="9">매출원가</th>
              <td class="item-cell" rowspan="3">재료비</td>
              <td>국내재</td>
              <td><a-input-number v-model:value="form.sales_domestic_material_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_domestic_material_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_domestic_material_note" /></td>
            </tr>
            <tr>
              <td>외자재</td>
              <td><a-input-number v-model:value="form.sales_overseas_material_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_overseas_material_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_overseas_material_note" /></td>
            </tr>
            <tr>
              <td>외주비</td>
              <td><a-input-number v-model:value="form.sales_outsourcing_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_outsourcing_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_outsourcing_note" /></td>
            </tr>
            <tr>
              <td class="item-cell" colspan="2">노무비</td>
              <td><a-input-number v-model:value="form.sales_labor_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_labor_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_labor_note" /></td>
            </tr>
            <tr>
              <td class="item-cell" colspan="2">경비</td>
              <td><a-input-number v-model:value="form.sales_expense_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_expense_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_expense_note" /></td>
            </tr>
            <tr class="summary-row">
              <td class="item-cell" colspan="2">소계 (직접원가)</td>
              <td class="readonly-amount">{{ formatAmount(directCostSubtotal) }}</td>
              <td class="ratio-cell">{{ costRatio(directCostSubtotal) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_direct_cost_note" /></td>
            </tr>
            <tr>
              <td class="item-cell">간접비</td>
              <td>일반관리비 등</td>
              <td><a-input-number v-model:value="form.sales_indirect_cost" :min="0" :formatter="amountFormatter" :parser="amountParser" /></td>
              <td class="ratio-cell">{{ costRatio(form.sales_indirect_cost) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_indirect_note" /></td>
            </tr>
            <tr class="summary-row">
              <td class="item-cell" colspan="2">합계 (매출원가 합계)</td>
              <td class="readonly-amount">{{ formatAmount(salesCostTotal) }}</td>
              <td class="ratio-cell">{{ costRatio(salesCostTotal) }}</td>
              <td class="note-cell"><a-input v-model:value="form.sales_cost_total_note" /></td>
            </tr>
            <tr class="profit-row">
              <td class="item-cell" colspan="2">세전이익 / 매출이익율</td>
              <td class="readonly-amount">{{ formatAmount(preTaxProfit) }}</td>
              <td class="ratio-cell">{{ costRatio(preTaxProfit) }}</td>
              <td class="note-cell"><a-input v-model:value="form.pre_tax_profit_note" /></td>
            </tr>
          </tbody>
        </table>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">담당자</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="담당 PM" name="pm_name">
              <a-select
                v-model:value="form.pm_employee_code"
                allow-clear
                show-search
                placeholder="PM 선택"
                :options="employeeOptions"
                option-filter-prop="searchText"
                @change="onPmEmployeeChange"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="PM 부서" name="pm_dept">
              <a-select
                v-model:value="form.pm_dept"
                allow-clear
                show-search
                placeholder="부서 선택"
                :options="departmentOptions"
                option-filter-prop="label"
                option-label-prop="shortLabel"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="영업 담당자" name="sales_manager">
              <a-input v-model:value="form.sales_manager" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="실행 담당자" name="execution_manager">
              <a-input v-model:value="form.execution_manager" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="수금 담당자" name="collection_manager">
              <a-input v-model:value="form.collection_manager" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button @click="closeProjectEditor">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-modal>

    <a-modal
      :mask-closable="false"
      v-model:open="businessCategoryModalOpen"
      title="사업구분 관리"
      width="460px"
      ok-text="닫기"
      :cancel-button-props="{ style: { display: 'none' } }"
      @ok="businessCategoryModalOpen = false"
    >
      <a-space-compact style="width:100%; margin-bottom:12px">
        <a-input
          v-model:value="businessCategoryDraft"
          placeholder="사업구분 입력"
          @pressEnter="addBusinessCategory"
        />
        <a-button type="primary" @click="addBusinessCategory">추가</a-button>
      </a-space-compact>
      <div class="category-tags">
        <a-tag
          v-for="category in businessCategories"
          :key="category"
          closable
          @close.prevent="removeBusinessCategory(category)"
        >
          {{ category }}
        </a-tag>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { Modal, message } from 'ant-design-vue'
import {
  ProjectOutlined, PlayCircleOutlined, CheckCircleOutlined, PauseCircleOutlined, PlusOutlined,
  DownloadOutlined, UploadOutlined,
} from '@ant-design/icons-vue'
import { executionApi, masterApi, managementApi } from '@/api'
import { useAuthStore } from '@/store/auth'
import { normalizeRole } from '@/utils/permissions'
import { flattenDepartmentTree } from '@/utils/departments'

const REQ_MARKER = '\n---프로젝트리스트요구사항---\n'
const CONTRACT_FORMS = ['원도급', '하도급', '공동도급', '위탁', '기타']
const BUSINESS_CATEGORY_STORAGE_KEY = 'project_business_categories'
const DEFAULT_BUSINESS_CATEGORIES = ['빌딩', 'DC', 'BAS', 'E&M', 'O&M', 'DR', 'FEMS리스', 'SE', '솔루션', 'CS', '스테콤', 'SCADA']
const SPG_OPTIONS = ['ES', 'BAS', 'IBS']
const REVENUE_TYPES = ['상품매출', '시운전', '유지보수', '서비스', '공사진행율']
const WORK_TYPES = ['전기', '통신', '기계설비']
const MONTH_LABELS = Array.from({ length: 12 }, (_, index) => `${index + 1}월`)
const SALES_PURCHASE_TAB_ROLES = new Set([
  'system_admin',
  'purchase_staff',
  'purchase_manager',
  'accounting_staff',
  'accounting_manager',
])
const COST_META_KEYS = [
  'contract_material_cost', 'contract_labor_cost',
  'contract_material_note', 'contract_labor_note', 'contract_total_note',
  'sales_domestic_material_cost', 'sales_overseas_material_cost', 'sales_outsourcing_cost',
  'sales_labor_cost', 'sales_expense_cost', 'sales_indirect_cost',
  'sales_domestic_material_note', 'sales_overseas_material_note', 'sales_outsourcing_note',
  'sales_labor_note', 'sales_expense_note', 'sales_direct_cost_note',
  'sales_indirect_note', 'sales_cost_total_note', 'pre_tax_profit_note',
]
const COST_DB_AMOUNT_KEYS = [
  'contract_material_cost', 'contract_labor_cost',
  'sales_domestic_material_cost', 'sales_overseas_material_cost', 'sales_outsourcing_cost',
  'sales_labor_cost', 'sales_expense_cost', 'sales_indirect_cost',
]
const COST_NOTE_KEYS = COST_META_KEYS.filter(key => key.endsWith('_note'))
const costAmountColumnKeys = [
  'contract_material_cost', 'contract_labor_cost', 'contract_detail_total',
  'sales_material_cost_total', 'sales_labor_cost', 'sales_expense_cost',
  'sales_direct_cost_subtotal', 'sales_indirect_cost', 'sales_cost_total', 'pre_tax_profit',
]
const salesPlanTextKeys = new Set(['project_name', 'contract_company', 'months'])
const salesPlanDateKeys = new Set(['contract_date', 'completion_date'])
const salesPlanAmountKeys = new Set([
  'contract_material_cost', 'contract_labor_cost',
  'order_tax_invoice_bl', 'order_progress_bl', 'current_order_amount',
  ...MONTH_LABELS.map(month => `order_${month}`),
  'order_balance_adjustment', 'overhead_amount', 'revised_bl_order_balance',
  'current_order_balance_progress', 'revenue_accumulated',
  ...MONTH_LABELS.map(month => `revenue_progress_${month}`),
  'previous_revenue_accumulated',
  'previous_tax_invoice_revenue_accumulated',
  'tax_invoice_order_balance', 'tax_invoice_revenue_accumulated',
  ...MONTH_LABELS.map(month => `tax_invoice_revenue_${month}`),
  'receivable_bl', 'vat_included_revenue_accumulated', 'current_year_collection_accumulated',
  ...MONTH_LABELS.map(month => `collection_${month}`),
  'bad_debt_writeoff', 'accounts_receivable',
])
const salesPlanCalculatedKeys = new Set([
  'current_order_balance_progress',
  'revenue_accumulated',
  'tax_invoice_order_balance',
  'tax_invoice_revenue_accumulated',
  'vat_included_revenue_accumulated',
  'current_year_collection_accumulated',
  ...MONTH_LABELS.map(month => `collection_${month}`),
  'accounts_receivable',
])
const purchaseMonthPrefixes = [
  'input_amount',
  'material_input',
  'foreign_material_input',
  'domestic_material_input',
  'subcontract_input',
  'individual_cost',
  'direct_expense',
  'labor_cost',
]
const purchasePlanTextKeys = new Set(['project_name', 'contract_company', 'months'])
const purchasePlanDateKeys = new Set(['contract_date', 'completion_date'])
const purchasePlanCalculatedKeys = new Set([
  'contract_total_amount',
  'ordered_cost_total',
  'expected_cost_total',
  'material_subcontract_total',
  'material_ratio',
  'remaining_material_cost',
  'accumulated_input_amount',
  'current_year_input_total',
  'material_input_total',
  'foreign_material_input_total',
  'domestic_material_input_total',
  'subcontract_input_total',
  'individual_cost_total',
  'direct_expense_total',
  'labor_cost_total',
  ...MONTH_LABELS.map(month => `input_amount_${month}`),
  ...MONTH_LABELS.map(month => `material_input_${month}`),
  ...MONTH_LABELS.map(month => `individual_cost_${month}`),
])
const purchasePlanManualAmountKeys = new Set([
  'contract_material_cost',
  'contract_labor_cost',
  'ordered_foreign_material_cost',
  'ordered_domestic_material_cost',
  'ordered_material_cost',
  'ordered_subcontract_cost',
  'ordered_individual_cost',
  'expected_foreign_material_cost',
  'expected_domestic_material_cost',
  'expected_material_cost',
  'expected_subcontract_cost',
  'expected_individual_cost',
  'previous_input_accumulated',
  'previous_material_input_accumulated',
  'previous_foreign_material_input_accumulated',
  'previous_domestic_material_input_accumulated',
  'previous_subcontract_input_accumulated',
  'previous_individual_cost_input_accumulated',
  'previous_direct_expense_input_accumulated',
  'previous_labor_cost_input_accumulated',
  ...['foreign_material_input', 'domestic_material_input', 'subcontract_input', 'direct_expense', 'labor_cost']
    .flatMap(prefix => MONTH_LABELS.map(month => `${prefix}_${month}`)),
])
const purchasePlanAmountKeys = new Set([
  ...purchasePlanManualAmountKeys,
  ...purchasePlanCalculatedKeys,
])
const domesticOverseasOptions = [
  { value: '내수', label: '내수' },
  { value: '해외', label: '해외' },
]
const specialRelationOptions = [
  { value: '특수관계', label: '특수관계' },
  { value: 'x', label: 'x' },
]
const salesProgressOptions = [
  { value: '진행', label: '진행' },
  { value: '종료', label: '종료' },
]

const items     = ref([])
const companies = ref([])
const departments = ref([])
const employees = ref([])
const orgYear = new Date().getFullYear()
const receivables = ref([])
const previousSalesPlanRows = ref([])
const salesPlanRows = ref([])
const salesPlanDirty = ref(false)
const previousPurchasePlanRows = ref([])
const purchasePlanRows = ref([])
const purchasePlanDirty = ref(false)
const loading   = ref(false)
const saving    = ref(false)
const importing = ref(false)
const drawerOpen = ref(false)
const businessCategoryModalOpen = ref(false)
const businessCategoryDraft = ref('')
const editItem  = ref(null)
const formRef   = ref()
const excelInput = ref()
const selectedId = ref(null)
const activeTab = ref('orders')
const auth = useAuthStore()
const projectEditorSnapshot = ref('')
const projectCancelConfirmOpen = ref(false)

const statusColor = { 미진행: 'orange', 진행중: 'blue', 완료: 'green' }
const canAccessSalesPurchaseTabs = computed(() =>
  SALES_PURCHASE_TAB_ROLES.has(normalizeRole(auth.user?.role))
)

watch(canAccessSalesPurchaseTabs, (allowed) => {
  if (!allowed && ['sales', 'purchases'].includes(activeTab.value)) {
    activeTab.value = 'orders'
  }
}, { immediate: true })

watch(drawerOpen, (open) => {
  if (open) {
    document.addEventListener('mousedown', handleProjectEditorOutsideMouseDown, true)
  } else {
    document.removeEventListener('mousedown', handleProjectEditorOutsideMouseDown, true)
  }
})

// ── 필터 ──
const filters = reactive({
  search: '', client_name: '', pm_dept: '',
  contract_from: null, contract_to: null,
  construct_from: null, construct_to: null,
  amount_from: null, amount_to: null,
  statuses: ['미진행', '진행중', '완료'],
  contract_forms: [],
  contract_types: [],
})

function resetFilters() {
  Object.assign(filters, {
    search: '', client_name: '', pm_dept: '',
    contract_from: null, contract_to: null,
    construct_from: null, construct_to: null,
    amount_from: null, amount_to: null,
    statuses: ['미진행', '진행중', '완료'],
    contract_forms: [], contract_types: [],
  })
}

// ── 클라이언트 필터링 ──
const filtered = computed(() => items.value.filter(d => {
  if (filters.search && !d.project_name?.toLowerCase().includes(filters.search.toLowerCase())
      && !d.project_no?.toLowerCase().includes(filters.search.toLowerCase())) return false
  if (filters.client_name && !d.client_name?.toLowerCase().includes(filters.client_name.toLowerCase())) return false
  if (filters.pm_dept && d.pm_dept !== filters.pm_dept) return false
  if (filters.contract_from && d.contract_start && d.contract_start < filters.contract_from) return false
  if (filters.contract_to   && d.contract_end   && d.contract_end   > filters.contract_to)   return false
  if (filters.construct_from && d.construct_start && d.construct_start < filters.construct_from) return false
  if (filters.construct_to   && d.construct_end   && d.construct_end   > filters.construct_to)   return false
  if (filters.amount_from != null && d.contract_amount < filters.amount_from) return false
  if (filters.amount_to   != null && d.contract_amount > filters.amount_to)   return false
  if (filters.statuses.length < 3 && !filters.statuses.includes(d.status)) return false
  if (filters.contract_forms.length > 0 && !filters.contract_forms.includes(d.contract_form)) return false
  if (filters.contract_types.length > 0 && !filters.contract_types.includes(d.contract_type)) return false
  return true
}))

// ── 통계 카드 ──
const statsCards = computed(() => {
  const all = items.value
  return [
    { key: 'total',   label: '전체 프로젝트', value: all.length,                                         color: '#1a2535', cls: '', iconCls: 'icon-gray', icon: ProjectOutlined },
    { key: 'active',  label: '진행중',        value: all.filter(d => d.status === '진행중').length,  color: '#1677ff', cls: 'stat-blue',   iconCls: 'icon-blue',   icon: PlayCircleOutlined },
    { key: 'done',    label: '완료',          value: all.filter(d => d.status === '완료').length,    color: '#52c41a', cls: 'stat-green',  iconCls: 'icon-green',  icon: CheckCircleOutlined },
    { key: 'pending', label: '미진행',        value: all.filter(d => d.status === '미진행').length,  color: '#fa8c16', cls: 'stat-orange', iconCls: 'icon-orange', icon: PauseCircleOutlined },
  ]
})

function salesPlanLeaf(title, key, width = 110, align = 'center', extra = {}) {
  return { title, key, dataIndex: key, width, align, ...extra }
}

function salesPlanMonthColumns(prefix, suffix = '', width = 105) {
  return MONTH_LABELS.map(month => salesPlanLeaf(`${month}${suffix}`, `${prefix}_${month}`, width, 'right'))
}

const salesPlanColumns = [
  salesPlanLeaf('JOB NO', 'job_no', 150, 'center', { fixed: 'left' }),
  salesPlanLeaf('프로젝트명', 'project_name', 180, 'center', { ellipsis: true, fixed: 'left' }),
  salesPlanLeaf('계약업체명', 'contract_company', 150, 'center', { ellipsis: true }),
  salesPlanLeaf('내수/해외', 'domestic_overseas', 100),
  salesPlanLeaf('특수관계', 'special_relation', 100),
  salesPlanLeaf('진행/종료', 'progress_status', 100),
  salesPlanLeaf('계약일', 'contract_date', 125),
  salesPlanLeaf('준공일', 'completion_date', 125),
  salesPlanLeaf('개월수', 'months', 80),
  {
    title: '계약금액',
    align: 'center',
    children: [
      salesPlanLeaf('총계약금액', 'contract_total_amount', 135, 'right'),
      salesPlanLeaf('자재비', 'contract_material_cost', 125, 'right'),
      salesPlanLeaf('노무비', 'contract_labor_cost', 125, 'right'),
    ],
  },
  {
    title: `${orgYear}년 수주`,
    align: 'center',
    children: [
      salesPlanLeaf('수주 B/L(계산서)', 'order_tax_invoice_bl', 140, 'right'),
      salesPlanLeaf('수주 B/L(진행)', 'order_progress_bl', 130, 'right'),
      salesPlanLeaf('現수주액', 'current_order_amount', 125, 'right'),
      ...salesPlanMonthColumns('order'),
      salesPlanLeaf('수주잔고정리', 'order_balance_adjustment', 125, 'right'),
      salesPlanLeaf('O/H', 'overhead_amount', 105, 'right'),
      salesPlanLeaf('수정 B/L수주잔', 'revised_bl_order_balance', 140, 'right'),
    ],
  },
  {
    title: '매출(진행율 인식 및 선수금 조정)',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 매출 누계`, 'previous_revenue_accumulated', 155, 'right'),
      salesPlanLeaf('現수주잔고(진행율기준)', 'current_order_balance_progress', 170, 'right'),
      salesPlanLeaf('매출누계', 'revenue_accumulated', 125, 'right'),
      ...salesPlanMonthColumns('revenue_progress', '매출'),
    ],
  },
  {
    title: '매출 세금계산서 발행 실적',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 매출 세금계산서 누계`, 'previous_tax_invoice_revenue_accumulated', 190, 'right'),
      salesPlanLeaf('수주잔(계산서)', 'tax_invoice_order_balance', 135, 'right'),
      salesPlanLeaf('매출누계', 'tax_invoice_revenue_accumulated', 125, 'right'),
      ...salesPlanMonthColumns('tax_invoice_revenue', '매출'),
    ],
  },
  {
    title: '수금현황',
    align: 'center',
    children: [
      salesPlanLeaf('채권B/L', 'receivable_bl', 115, 'right'),
      salesPlanLeaf('VAT포함매출누계', 'vat_included_revenue_accumulated', 150, 'right'),
      salesPlanLeaf('당년수금누계', 'current_year_collection_accumulated', 135, 'right'),
      ...salesPlanMonthColumns('collection', '수금'),
      salesPlanLeaf('채권제각', 'bad_debt_writeoff', 115, 'right'),
      salesPlanLeaf('외상매출금', 'accounts_receivable', 125, 'right'),
    ],
  },
  salesPlanLeaf('관리', 'action', 80, 'center', { fixed: 'right' }),
]

const salesPlanScrollX = 8450

function purchasePlanMonthColumns(prefix, width = 105) {
  return MONTH_LABELS.map(month => salesPlanLeaf(month, `${prefix}_${month}`, width, 'right'))
}

const purchasePlanColumns = [
  salesPlanLeaf('JOB NO', 'job_no', 150, 'center', { fixed: 'left' }),
  salesPlanLeaf('프로젝트명', 'project_name', 180, 'center', { ellipsis: true, fixed: 'left' }),
  salesPlanLeaf('계약업체명', 'contract_company', 150, 'center', { ellipsis: true }),
  salesPlanLeaf('내수/해외', 'domestic_overseas', 100),
  salesPlanLeaf('특수관계', 'special_relation', 100),
  salesPlanLeaf('진행/종료', 'progress_status', 100),
  salesPlanLeaf('계약일', 'contract_date', 125),
  salesPlanLeaf('준공일', 'completion_date', 125),
  salesPlanLeaf('개월수', 'months', 80),
  {
    title: '계약금액',
    align: 'center',
    children: [
      salesPlanLeaf('총 계약금액', 'contract_total_amount', 135, 'right'),
      salesPlanLeaf('자재비', 'contract_material_cost', 125, 'right'),
      salesPlanLeaf('노무비', 'contract_labor_cost', 125, 'right'),
    ],
  },
  {
    title: '수주원가',
    align: 'center',
    children: [
      salesPlanLeaf('외자', 'ordered_foreign_material_cost', 120, 'right'),
      salesPlanLeaf('내자', 'ordered_domestic_material_cost', 120, 'right'),
      salesPlanLeaf('자재비', 'ordered_material_cost', 120, 'right'),
      salesPlanLeaf('외주비', 'ordered_subcontract_cost', 120, 'right'),
      salesPlanLeaf('개별비', 'ordered_individual_cost', 120, 'right'),
      salesPlanLeaf('합계', 'ordered_cost_total', 120, 'right'),
    ],
  },
  {
    title: '예정원가',
    align: 'center',
    children: [
      salesPlanLeaf('외자', 'expected_foreign_material_cost', 120, 'right'),
      salesPlanLeaf('내자', 'expected_domestic_material_cost', 120, 'right'),
      salesPlanLeaf('자재비', 'expected_material_cost', 120, 'right'),
      salesPlanLeaf('외주비', 'expected_subcontract_cost', 120, 'right'),
      salesPlanLeaf('개별비', 'expected_individual_cost', 120, 'right'),
      salesPlanLeaf('합계', 'expected_cost_total', 120, 'right'),
      salesPlanLeaf('자재비+외주비', 'material_subcontract_total', 135, 'right'),
      salesPlanLeaf('재료비율', 'material_ratio', 110, 'center'),
    ],
  },
  salesPlanLeaf('잔여재료비', 'remaining_material_cost', 135, 'right'),
  salesPlanLeaf('누적투입금액', 'accumulated_input_amount', 140, 'right'),
  salesPlanLeaf(`${orgYear}년이전투입누계`, 'previous_input_accumulated', 150, 'right'),
  {
    title: `${orgYear}년 투입금액(자재+외주비)-노무비, 경비 제외`,
    align: 'center',
    children: [
      salesPlanLeaf('총투입금액', 'current_year_input_total', 130, 'right'),
      ...purchasePlanMonthColumns('input_amount'),
    ],
  },
  {
    title: '자재 투입',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 자재 투입 누계`, 'previous_material_input_accumulated', 175, 'right'),
      salesPlanLeaf('자재투입합', 'material_input_total', 130, 'right'),
      ...purchasePlanMonthColumns('material_input'),
    ],
  },
  {
    title: '외자재투입금액',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 외자재 투입 누계`, 'previous_foreign_material_input_accumulated', 185, 'right'),
      salesPlanLeaf('외자재투입합', 'foreign_material_input_total', 135, 'right'),
      ...purchasePlanMonthColumns('foreign_material_input'),
    ],
  },
  {
    title: '내자재투입금액',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 내자재 투입 누계`, 'previous_domestic_material_input_accumulated', 185, 'right'),
      salesPlanLeaf('내자재투입합', 'domestic_material_input_total', 135, 'right'),
      ...purchasePlanMonthColumns('domestic_material_input'),
    ],
  },
  {
    title: '외주비투입',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 외주비 투입 누계`, 'previous_subcontract_input_accumulated', 185, 'right'),
      salesPlanLeaf('외주비투입계', 'subcontract_input_total', 135, 'right'),
      ...purchasePlanMonthColumns('subcontract_input'),
    ],
  },
  {
    title: '개별비',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 개별비 투입 누계`, 'previous_individual_cost_input_accumulated', 185, 'right'),
      salesPlanLeaf('개별비계', 'individual_cost_total', 120, 'right'),
      ...purchasePlanMonthColumns('individual_cost'),
    ],
  },
  {
    title: '직접경비',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 직접경비 투입 누계`, 'previous_direct_expense_input_accumulated', 195, 'right'),
      salesPlanLeaf('직접경비계', 'direct_expense_total', 120, 'right'),
      ...purchasePlanMonthColumns('direct_expense'),
    ],
  },
  {
    title: '인건비',
    align: 'center',
    children: [
      salesPlanLeaf(`${String(orgYear).slice(2)}년 이전 인건비 투입 누계`, 'previous_labor_cost_input_accumulated', 185, 'right'),
      salesPlanLeaf('인건비 계', 'labor_cost_total', 120, 'right'),
      ...purchasePlanMonthColumns('labor_cost'),
    ],
  },
  salesPlanLeaf('관리', 'action', 80, 'center', { fixed: 'right' }),
]

const purchasePlanScrollX = 12900

// ── 테이블 컬럼 ──
const columns = [
  { title: 'No',        key: 'no',               width: 55,  align: 'center',
    customRender: ({ index }) => index + 1 },
  { title: 'PJT NO.',   dataIndex: 'project_no',  width: 140, align: 'center' },
  { title: 'PJT명',     key: 'project_name',      width: 220, align: 'center', ellipsis: true },
  { title: '발주처',    dataIndex: 'client_name',  width: 160, align: 'center', ellipsis: true },
  { title: '사업부',    dataIndex: 'business_division', width: 150, align: 'center' },
  { title: '팀',        dataIndex: 'team_name',    width: 140, align: 'center' },
  { title: '사업구분',  dataIndex: 'business_category', width: 100, align: 'center' },
  { title: 'SPG',       dataIndex: 'spg',          width: 80,  align: 'center' },
  { title: '영업담당자', dataIndex: 'sales_manager', width: 100, align: 'center' },
  { title: '실행담당자', dataIndex: 'execution_manager', width: 100, align: 'center' },
  { title: '수금담당자', dataIndex: 'collection_manager', width: 100, align: 'center' },
  { title: '매출 유형', dataIndex: 'revenue_type', width: 110, align: 'center' },
  { title: '공종',      dataIndex: 'work_type',    width: 100, align: 'center' },
  { title: '수금조건',  dataIndex: 'collection_terms', width: 150, align: 'center', ellipsis: true },
  { title: '특수관계',  dataIndex: 'special_relation', width: 100, align: 'center' },
  { title: '고용보험',  key: 'employment_insurance', width: 90, align: 'center' },
  { title: '산재보험',  key: 'industrial_accident_insurance', width: 90, align: 'center' },
  { title: '착공 시작', dataIndex: 'construct_start', width: 110, align: 'center' },
  { title: '착공 종료', dataIndex: 'construct_end',   width: 110, align: 'center' },
  { title: '계약금액',  key: 'contract_amount',   width: 140, align: 'right' },
  { title: '계약 자재비', key: 'contract_material_cost', width: 135, align: 'right' },
  { title: '계약 노무비', key: 'contract_labor_cost', width: 135, align: 'right' },
  { title: '계약금액 합계', key: 'contract_detail_total', width: 140, align: 'right' },
  { title: '재료비 합계', key: 'sales_material_cost_total', width: 135, align: 'right' },
  { title: '노무비', key: 'sales_labor_cost', width: 135, align: 'right' },
  { title: '경비', key: 'sales_expense_cost', width: 135, align: 'right' },
  { title: '직접원가 소계', key: 'sales_direct_cost_subtotal', width: 140, align: 'right' },
  { title: '간접비', key: 'sales_indirect_cost', width: 135, align: 'right' },
  { title: '매출원가 합계', key: 'sales_cost_total', width: 140, align: 'right' },
  { title: '세전이익', key: 'pre_tax_profit', width: 135, align: 'right' },
  { title: '담당 PM',   dataIndex: 'pm_name',     width: 100, align: 'center' },
  { title: '진행상태',  key: 'status',            width: 110, align: 'center' },
  { title: '관리',      key: 'action',            width: 100, align: 'center', fixed: 'right' },
]

const salesColumns = [
  { title: 'No',        key: 'no',               width: 55,  align: 'center',
    customRender: ({ index }) => index + 1 },
  { title: 'PJT NO.',   dataIndex: 'project_no', width: 140, align: 'center' },
  { title: 'PJT명',     dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '발주처',    dataIndex: 'client_name', width: 160, align: 'center', ellipsis: true },
  { title: '사업부',    dataIndex: 'business_division', width: 150, align: 'center' },
  { title: '팀',        dataIndex: 'team_name', width: 140, align: 'center' },
  { title: '매출 유형', dataIndex: 'revenue_type', width: 120, align: 'center' },
  { title: '계약금액',  key: 'contract_amount', width: 140, align: 'right' },
  { title: '매출원가 합계', key: 'sales_cost_total', width: 140, align: 'right' },
  { title: '세전이익', key: 'pre_tax_profit', width: 135, align: 'right' },
  { title: '수금조건',  dataIndex: 'collection_terms', width: 170, align: 'center', ellipsis: true },
  { title: '영업담당자', dataIndex: 'sales_manager', width: 110, align: 'center' },
  { title: '수금담당자', dataIndex: 'collection_manager', width: 110, align: 'center' },
  { title: '진행상태',  key: 'status', width: 110, align: 'center' },
]

const purchaseColumns = [
  { title: 'No',        key: 'no',               width: 55,  align: 'center',
    customRender: ({ index }) => index + 1 },
  { title: 'PJT NO.',   dataIndex: 'project_no', width: 140, align: 'center' },
  { title: 'PJT명',     dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '발주처',    dataIndex: 'client_name', width: 160, align: 'center', ellipsis: true },
  { title: '사업부',    dataIndex: 'business_division', width: 150, align: 'center' },
  { title: '팀',        dataIndex: 'team_name', width: 140, align: 'center' },
  { title: '사업구분',  dataIndex: 'business_category', width: 110, align: 'center' },
  { title: 'SPG',       dataIndex: 'spg', width: 90, align: 'center' },
  { title: '공종',      dataIndex: 'work_type', width: 110, align: 'center' },
  { title: '실행담당자', dataIndex: 'execution_manager', width: 110, align: 'center' },
  { title: '계약금액',  key: 'contract_amount', width: 140, align: 'right' },
  { title: '재료비 합계', key: 'sales_material_cost_total', width: 135, align: 'right' },
  { title: '노무비', key: 'sales_labor_cost', width: 135, align: 'right' },
  { title: '경비', key: 'sales_expense_cost', width: 135, align: 'right' },
  { title: '매출원가 합계', key: 'sales_cost_total', width: 140, align: 'right' },
  { title: '진행상태',  key: 'status', width: 110, align: 'center' },
]

// ── 행 스타일 ──
function rowClass(record) {
  const classes = ['proj-row']
  if (selectedId.value === record.id) classes.push('proj-row--selected')
  if (isOverdue(record)) classes.push('proj-row--overdue')
  return classes.join(' ')
}

function isOverdue(record) {
  return record.status === '진행중' && record.construct_end &&
    record.construct_end < new Date().toISOString().slice(0, 10)
}

function handleRowClick(record) {
  selectedId.value = selectedId.value === record.id ? null : record.id
}

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function defaultCostValue(key) {
  return key.endsWith('_note') ? '' : 0
}

function normalizeCostMeta(source = {}) {
  return COST_META_KEYS.reduce((acc, key) => {
    const value = source?.[key]
    acc[key] = key.endsWith('_note') ? (value || '') : toNumber(value)
    return acc
  }, {})
}

function mergeCostMeta(req = {}, item = {}) {
  const merged = normalizeCostMeta(req)
  COST_DB_AMOUNT_KEYS.forEach((key) => {
    const itemValue = toNumber(item?.[key])
    if (itemValue || req?.[key] === undefined || req?.[key] === null) {
      merged[key] = itemValue
    }
  })
  COST_NOTE_KEYS.forEach((key) => {
    merged[key] = req?.[key] || ''
  })
  return merged
}

function calculateCostTotals(source = {}) {
  const contractDetailTotal = toNumber(source.contract_material_cost) + toNumber(source.contract_labor_cost)
  const salesMaterialCostTotal = toNumber(source.sales_domestic_material_cost)
    + toNumber(source.sales_overseas_material_cost)
    + toNumber(source.sales_outsourcing_cost)
  const salesDirectCostSubtotal = salesMaterialCostTotal
    + toNumber(source.sales_labor_cost)
    + toNumber(source.sales_expense_cost)
  const salesCostTotal = salesDirectCostSubtotal + toNumber(source.sales_indirect_cost)
  return {
    contract_detail_total: contractDetailTotal,
    sales_material_cost_total: salesMaterialCostTotal,
    sales_direct_cost_subtotal: salesDirectCostSubtotal,
    sales_cost_total: salesCostTotal,
    pre_tax_profit: toNumber(source.contract_amount) - salesCostTotal,
  }
}

function formatAmount(value) {
  const amount = toNumber(value)
  return amount ? amount.toLocaleString() : '—'
}

function formatPercent(value) {
  const amount = toNumber(value)
  return amount ? `${amount.toFixed(1)}%` : '0.0%'
}

function projectAmountValue(record, key) {
  const totals = calculateCostTotals(record)
  return key in totals ? totals[key] : record[key]
}

function costRatio(value, base = form.contract_amount) {
  const amount = toNumber(value)
  const total = toNumber(base)
  if (!total) return '0.0%'
  return `${((amount / total) * 100).toFixed(1)}%`
}

const amountFormatter = value => value ? Number(value).toLocaleString() : ''
const amountParser = value => String(value || '').replace(/,/g, '')

const jobNoAutoCompleteOptions = computed(() =>
  items.value.map(project => ({
    value: project.project_no || '',
    label: `${project.project_no || '-'} / ${project.project_name || '-'}`,
    projectId: project.id,
  }))
)

function createEmptySalesPlanRow() {
  const amountFields = Object.fromEntries([...salesPlanAmountKeys].map(key => [key, 0]))
  return {
    id: `sales-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    project_id: undefined,
    job_no: '',
    project_name: '',
    contract_company: '',
    domestic_overseas: '내수',
    special_relation: 'x',
    progress_status: '진행',
    contract_date: null,
    completion_date: null,
    months: '',
    ...amountFields,
  }
}

function normalizeSalesPlanRow(row = {}) {
  const empty = createEmptySalesPlanRow()
  const normalized = { ...empty, ...row }
  salesPlanAmountKeys.forEach(key => { normalized[key] = toNumber(normalized[key]) })
  return normalized
}

function salesPlanRowsForSave() {
  return salesPlanRows.value.map(row => ({
    ...row,
    ...Object.fromEntries(
      [...salesPlanCalculatedKeys].map(key => [key, salesPlanCalculatedValue(row, key)])
    ),
  }))
}

function markSalesPlanDirty() {
  salesPlanDirty.value = true
}

async function saveSalesPlanRows() {
  saving.value = true
  try {
    const res = await executionApi.saveProjectSalesPlans(orgYear, salesPlanRowsForSave())
    salesPlanRows.value = (res.data || []).map(normalizeSalesPlanRow)
    salesPlanDirty.value = false
    message.success('프로젝트리스트(매출)이 DB에 저장되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '프로젝트리스트(매출) 저장 오류')
  } finally {
    saving.value = false
  }
}

function addSalesPlanRow() {
  salesPlanRows.value = [...salesPlanRows.value, createEmptySalesPlanRow()]
  markSalesPlanDirty()
}

function removeSalesPlanRow(id) {
  salesPlanRows.value = salesPlanRows.value.filter(row => row.id !== id)
  markSalesPlanDirty()
}

function monthDiff(start, end) {
  if (!start || !end) return ''
  const startDate = new Date(start)
  const endDate = new Date(end)
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return ''
  const diff = (endDate.getFullYear() - startDate.getFullYear()) * 12
    + (endDate.getMonth() - startDate.getMonth())
  return String(Math.max(diff + 1, 0))
}

function salesRowContractTotal(row) {
  return toNumber(row.contract_material_cost) + toNumber(row.contract_labor_cost)
}

function findPreviousSalesPlanRow(project) {
  if (!project) return null
  return previousSalesPlanRows.value.find(row => row.project_id && row.project_id === project.id)
    || previousSalesPlanRows.value.find(row => row.job_no && row.job_no === project.project_no)
    || null
}

function salesPlanCarryoverFields(project) {
  const previousRow = findPreviousSalesPlanRow(project)
  if (!previousRow) return {}
  return {
    order_tax_invoice_bl: salesPlanCalculatedValue(previousRow, 'tax_invoice_order_balance', { useStoredCollections: true }),
    receivable_bl: salesPlanCalculatedValue(previousRow, 'accounts_receivable', { useStoredCollections: true }),
  }
}

function projectToSalesPlanBase(project) {
  const contractMaterial = toNumber(project.contract_material_cost)
  const contractLabor = toNumber(project.contract_labor_cost)
  return {
    project_id: project.id,
    job_no: project.project_no || '',
    project_name: project.project_name || '',
    contract_company: project.client_name || '',
    domestic_overseas: project.contract_type === '국외' ? '해외' : '내수',
    special_relation: project.special_relation === '특수관계' ? '특수관계' : 'x',
    progress_status: project.status === '완료' ? '종료' : '진행',
    contract_date: project.contract_start || null,
    completion_date: project.construct_end || project.contract_end || null,
    months: monthDiff(project.contract_start, project.construct_end || project.contract_end),
    contract_material_cost: contractMaterial || toNumber(project.contract_amount),
    contract_labor_cost: contractLabor,
  }
}

function applySalesPlanCarryover(row, project) {
  const carryover = salesPlanCarryoverFields(project)
  if (!toNumber(row.order_tax_invoice_bl) && toNumber(carryover.order_tax_invoice_bl)) {
    row.order_tax_invoice_bl = carryover.order_tax_invoice_bl
  }
  if (!toNumber(row.receivable_bl) && toNumber(carryover.receivable_bl)) {
    row.receivable_bl = carryover.receivable_bl
  }
}

function syncSalesPlanRowsWithProjects({ silent = false } = {}) {
  const existingByProjectId = new Map(
    salesPlanRows.value
      .filter(row => row.project_id)
      .map(row => [row.project_id, row])
  )
  const existingByJobNo = new Map(
    salesPlanRows.value
      .filter(row => row.job_no)
      .map(row => [row.job_no, row])
  )
  const syncedRows = [...salesPlanRows.value]
  let added = 0

  items.value.forEach(project => {
    const base = projectToSalesPlanBase(project)
    const existing = existingByProjectId.get(project.id) || existingByJobNo.get(base.job_no)
    if (existing) {
      Object.assign(existing, {
        project_id: base.project_id,
        job_no: base.job_no,
        project_name: base.project_name,
        contract_company: base.contract_company,
        domestic_overseas: base.domestic_overseas,
        special_relation: base.special_relation,
        progress_status: base.progress_status,
        contract_date: base.contract_date,
        completion_date: base.completion_date,
        months: base.months,
      })
      applySalesPlanCarryover(existing, project)
      return
    }
    const created = normalizeSalesPlanRow({ ...createEmptySalesPlanRow(), ...base, ...salesPlanCarryoverFields(project) })
    syncedRows.push(created)
    added += 1
  })

  salesPlanRows.value = syncedRows.map(normalizeSalesPlanRow)
  if (added > 0) salesPlanDirty.value = true
  if (!silent) {
    message.success(added ? `${added}개 수주 프로젝트를 매출 탭에 반영했습니다.` : '수주 프로젝트 정보가 최신 상태입니다.')
  }
}

function sumSalesPlanMonths(row, prefix) {
  return MONTH_LABELS.reduce((sum, month) => sum + toNumber(row[`${prefix}_${month}`]), 0)
}

function receivableMatchesSalesRow(receivable, row) {
  if (receivable.project_id && row.project_id && receivable.project_id === row.project_id) return true
  if (receivable.job_no && row.job_no && receivable.job_no === row.job_no) return true
  return Boolean(receivable.project_name && row.project_name && receivable.project_name === row.project_name)
}

function salesPlanCollectionAmount(row, monthLabel) {
  const monthNumber = Number(String(monthLabel).replace('월', ''))
  return receivables.value.reduce((sum, receivable) => {
    if (!receivableMatchesSalesRow(receivable, row)) return sum
    if (!receivable.collection_date) return sum
    const collectionDate = new Date(receivable.collection_date)
    if (Number.isNaN(collectionDate.getTime())) return sum
    if (collectionDate.getFullYear() !== orgYear || collectionDate.getMonth() + 1 !== monthNumber) return sum
    return sum + toNumber(receivable.collected_amount || receivable.amount)
  }, 0)
}

function salesPlanCollectionTotal(row) {
  return MONTH_LABELS.reduce((sum, month) => sum + salesPlanCollectionAmount(row, month), 0)
}

function salesPlanCalculatedValue(row, key, options = {}) {
  const revenueAccumulated = sumSalesPlanMonths(row, 'revenue_progress')
  const taxInvoiceRevenueAccumulated = sumSalesPlanMonths(row, 'tax_invoice_revenue')
  const taxInvoiceOrderBalance = toNumber(row.order_tax_invoice_bl)
    + toNumber(row.current_order_amount)
    - toNumber(row.order_balance_adjustment)
    - taxInvoiceRevenueAccumulated
  const vatIncludedRevenueAccumulated = row.domestic_overseas === '내수'
    ? taxInvoiceOrderBalance * 1.1
    : taxInvoiceOrderBalance
  const currentYearCollectionAccumulated = options.useStoredCollections
    ? sumSalesPlanMonths(row, 'collection')
    : salesPlanCollectionTotal(row)

  if (key.startsWith('collection_')) {
    if (options.useStoredCollections) return toNumber(row[key])
    return salesPlanCollectionAmount(row, key.replace('collection_', ''))
  }

  switch (key) {
    case 'current_order_balance_progress':
      return toNumber(row.order_progress_bl)
        + toNumber(row.current_order_amount)
        - toNumber(row.order_balance_adjustment)
        - revenueAccumulated
    case 'revenue_accumulated':
      return revenueAccumulated
    case 'tax_invoice_order_balance':
      return taxInvoiceOrderBalance
    case 'tax_invoice_revenue_accumulated':
      return taxInvoiceRevenueAccumulated
    case 'vat_included_revenue_accumulated':
      return vatIncludedRevenueAccumulated
    case 'current_year_collection_accumulated':
      return currentYearCollectionAccumulated
    case 'accounts_receivable':
      return toNumber(row.receivable_bl)
        + vatIncludedRevenueAccumulated
        - currentYearCollectionAccumulated
    default:
      return toNumber(row[key])
  }
}

function applyProjectToSalesRow(row, projectId) {
  const project = items.value.find(item => item.id === projectId)
  if (!project) {
    Object.assign(row, {
      project_id: undefined,
      job_no: '',
      project_name: '',
      contract_company: '',
    })
    markSalesPlanDirty()
    return
  }
  Object.assign(row, projectToSalesPlanBase(project))
  applySalesPlanCarryover(row, project)
  markSalesPlanDirty()
}

// ── 폼 ──
function createEmptyPurchasePlanRow() {
  const amountFields = Object.fromEntries([...purchasePlanAmountKeys].map(key => [key, 0]))
  return {
    id: `purchase-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    project_id: undefined,
    job_no: '',
    project_name: '',
    contract_company: '',
    domestic_overseas: '내수',
    special_relation: 'x',
    progress_status: '진행',
    contract_date: null,
    completion_date: null,
    months: '',
    ...amountFields,
  }
}

function normalizePurchasePlanRow(row = {}) {
  const empty = createEmptyPurchasePlanRow()
  const normalized = { ...empty, ...row }
  purchasePlanAmountKeys.forEach(key => { normalized[key] = toNumber(normalized[key]) })
  return normalized
}

function sumPurchasePlanMonths(row, prefix) {
  return MONTH_LABELS.reduce((sum, month) => sum + toNumber(row[`${prefix}_${month}`]), 0)
}

function sumPurchaseCalculatedMonths(row, prefix) {
  return MONTH_LABELS.reduce((sum, month) => sum + purchasePlanCalculatedValue(row, `${prefix}_${month}`), 0)
}

function purchasePlanCalculatedValue(row, key) {
  const contractTotalAmount = toNumber(row.contract_material_cost) + toNumber(row.contract_labor_cost)
  const orderedCostTotal = toNumber(row.ordered_foreign_material_cost)
    + toNumber(row.ordered_domestic_material_cost)
    + toNumber(row.ordered_material_cost)
    + toNumber(row.ordered_subcontract_cost)
    + toNumber(row.ordered_individual_cost)
  const expectedCostTotal = toNumber(row.expected_foreign_material_cost)
    + toNumber(row.expected_domestic_material_cost)
    + toNumber(row.expected_material_cost)
    + toNumber(row.expected_subcontract_cost)
    + toNumber(row.expected_individual_cost)
  const materialSubcontractTotal = toNumber(row.expected_material_cost) + toNumber(row.expected_subcontract_cost)

  if (key.startsWith('input_amount_')) {
    const month = key.replace('input_amount_', '')
    return purchasePlanCalculatedValue(row, `material_input_${month}`)
      + toNumber(row[`subcontract_input_${month}`])
  }
  if (key.startsWith('material_input_')) {
    const month = key.replace('material_input_', '')
    return toNumber(row[`foreign_material_input_${month}`])
      + toNumber(row[`domestic_material_input_${month}`])
  }
  if (key.startsWith('individual_cost_')) {
    const month = key.replace('individual_cost_', '')
    return toNumber(row[`direct_expense_${month}`])
      + toNumber(row[`labor_cost_${month}`])
  }

  const currentYearInputTotal = sumPurchaseCalculatedMonths(row, 'input_amount')
  const accumulatedInputAmount = toNumber(row.previous_input_accumulated) + currentYearInputTotal

  switch (key) {
    case 'contract_total_amount':
      return contractTotalAmount
    case 'ordered_cost_total':
      return orderedCostTotal
    case 'expected_cost_total':
      return expectedCostTotal
    case 'material_subcontract_total':
      return materialSubcontractTotal
    case 'material_ratio':
      return contractTotalAmount ? (materialSubcontractTotal / contractTotalAmount) * 100 : 0
    case 'remaining_material_cost':
      return materialSubcontractTotal - accumulatedInputAmount
    case 'accumulated_input_amount':
      return accumulatedInputAmount
    case 'current_year_input_total':
      return currentYearInputTotal
    case 'material_input_total':
      return sumPurchaseCalculatedMonths(row, 'material_input')
    case 'foreign_material_input_total':
      return sumPurchasePlanMonths(row, 'foreign_material_input')
    case 'domestic_material_input_total':
      return sumPurchasePlanMonths(row, 'domestic_material_input')
    case 'subcontract_input_total':
      return sumPurchasePlanMonths(row, 'subcontract_input')
    case 'individual_cost_total':
      return sumPurchaseCalculatedMonths(row, 'individual_cost')
    case 'direct_expense_total':
      return sumPurchasePlanMonths(row, 'direct_expense')
    case 'labor_cost_total':
      return sumPurchasePlanMonths(row, 'labor_cost')
    default:
      return toNumber(row[key])
  }
}

function purchasePlanRowsForSave() {
  return purchasePlanRows.value.map(row => ({
    ...row,
    ...Object.fromEntries(
      [...purchasePlanCalculatedKeys].map(key => [key, purchasePlanCalculatedValue(row, key)])
    ),
  }))
}

function findPreviousPurchasePlanRow(project) {
  if (!project) return null
  return previousPurchasePlanRows.value.find(row => row.project_id && row.project_id === project.id)
    || previousPurchasePlanRows.value.find(row => row.job_no && row.job_no === project.project_no)
    || null
}

function purchasePlanCarryoverFields(project) {
  const previousRow = findPreviousPurchasePlanRow(project)
  if (!previousRow) return {}
  return {
    previous_input_accumulated: purchasePlanCalculatedValue(previousRow, 'accumulated_input_amount'),
  }
}

function projectToPurchasePlanBase(project) {
  return projectToSalesPlanBase(project)
}

function applyPurchasePlanCarryover(row, project) {
  const carryover = purchasePlanCarryoverFields(project)
  if (!toNumber(row.previous_input_accumulated) && toNumber(carryover.previous_input_accumulated)) {
    row.previous_input_accumulated = carryover.previous_input_accumulated
  }
}

function markPurchasePlanDirty() {
  purchasePlanDirty.value = true
}

async function savePurchasePlanRows() {
  saving.value = true
  try {
    const res = await executionApi.saveProjectPurchasePlans(orgYear, purchasePlanRowsForSave())
    purchasePlanRows.value = (res.data || []).map(normalizePurchasePlanRow)
    purchasePlanDirty.value = false
    message.success('프로젝트리스트(매입)이 DB에 저장되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '프로젝트리스트(매입) 저장 오류')
  } finally {
    saving.value = false
  }
}

function addPurchasePlanRow() {
  purchasePlanRows.value = [...purchasePlanRows.value, createEmptyPurchasePlanRow()]
  markPurchasePlanDirty()
}

function removePurchasePlanRow(id) {
  purchasePlanRows.value = purchasePlanRows.value.filter(row => row.id !== id)
  markPurchasePlanDirty()
}

function applyProjectToPurchaseRow(row, projectId) {
  const project = items.value.find(item => item.id === projectId)
  if (!project) {
    Object.assign(row, {
      project_id: undefined,
      job_no: '',
      project_name: '',
      contract_company: '',
    })
    markPurchasePlanDirty()
    return
  }
  Object.assign(row, projectToPurchasePlanBase(project))
  applyPurchasePlanCarryover(row, project)
  markPurchasePlanDirty()
}

function syncPurchasePlanRowsWithProjects({ silent = false } = {}) {
  const existingByProjectId = new Map(
    purchasePlanRows.value
      .filter(row => row.project_id)
      .map(row => [row.project_id, row])
  )
  const existingByJobNo = new Map(
    purchasePlanRows.value
      .filter(row => row.job_no)
      .map(row => [row.job_no, row])
  )
  const syncedRows = [...purchasePlanRows.value]
  let added = 0

  items.value.forEach(project => {
    const base = projectToPurchasePlanBase(project)
    const existing = existingByProjectId.get(project.id) || existingByJobNo.get(base.job_no)
    if (existing) {
      Object.assign(existing, {
        project_id: base.project_id,
        job_no: base.job_no,
        project_name: base.project_name,
        contract_company: base.contract_company,
        domestic_overseas: base.domestic_overseas,
        special_relation: base.special_relation,
        progress_status: base.progress_status,
        contract_date: base.contract_date,
        completion_date: base.completion_date,
        months: base.months,
      })
      applyPurchasePlanCarryover(existing, project)
      return
    }
    const created = normalizePurchasePlanRow({ ...createEmptyPurchasePlanRow(), ...base, ...purchasePlanCarryoverFields(project) })
    syncedRows.push(created)
    added += 1
  })

  purchasePlanRows.value = syncedRows.map(normalizePurchasePlanRow)
  if (added > 0) purchasePlanDirty.value = true
  if (!silent) {
    message.success(added ? `${added}개 수주 프로젝트를 매입 탭에 반영했습니다.` : '수주 프로젝트 정보가 최신 상태입니다.')
  }
}

const emptyForm = {
  project_no: '', project_name: '', client_id: null, client_name: '',
  contract_form: '원도급', contract_type: '국내', status: '미진행',
  contract_amount: 0, contract_rate: 0,
  contract_start: null, contract_end: null,
  construct_start: null, construct_end: null,
  pm_employee_code: null,
  pm_name: '', pm_dept: '', region: '', notes: '',
  business_division: undefined, team_name: '', business_category: undefined, spg: undefined,
  sales_manager: '', execution_manager: '', collection_manager: '',
  revenue_type: undefined, work_type: undefined, collection_terms: '',
  warranty_period: '', special_relation: 'x',
  employment_insurance: false, industrial_accident_insurance: false,
  ...normalizeCostMeta(Object.fromEntries(COST_META_KEYS.map(key => [key, defaultCostValue(key)]))),
}
const form = reactive({ ...emptyForm })
const businessCategories = ref([...DEFAULT_BUSINESS_CATEGORIES])
const businessCategoryOptions = computed(() => businessCategories.value)

const contractDetailTotal = computed(() => calculateCostTotals(form).contract_detail_total)
const materialCostTotal = computed(() => calculateCostTotals(form).sales_material_cost_total)
const directCostSubtotal = computed(() => calculateCostTotals(form).sales_direct_cost_subtotal)
const salesCostTotal = computed(() => calculateCostTotals(form).sales_cost_total)
const preTaxProfit = computed(() => calculateCostTotals(form).pre_tax_profit)

const flatDepartments = computed(() => flattenDepartmentTree(departments.value))

const departmentOptions = computed(() =>
  flatDepartments.value
    .filter(dept => dept.is_active !== false)
    .map(dept => ({
      value: dept.name,
      label: dept.path,
      shortLabel: dept.name,
      deptType: dept.dept_type,
      rootName: dept.rootName,
    }))
)

const employeeOptions = computed(() =>
  employees.value
    .filter(emp => emp.is_active !== false)
    .map(emp => ({
      value: emp.emp_code,
      label: `${emp.name} (${emp.emp_code})${emp.department_name ? ` - ${emp.department_name}` : ''}`,
      searchText: `${emp.name} ${emp.emp_code} ${emp.department_name || ''}`,
      employee: emp,
    }))
)

const divisionOptions = computed(() =>
  flatDepartments.value
    .filter(dept => ['office', 'division', 'business'].includes(dept.dept_type))
    .map(dept => ({
      value: dept.name,
      label: dept.path,
      shortLabel: dept.name,
    }))
)

const teamOptions = computed(() =>
  flatDepartments.value
    .filter(dept => ['team', 'part'].includes(dept.dept_type))
    .map(dept => ({
      value: dept.name,
      label: dept.path,
      shortLabel: dept.name,
      rootName: dept.rootName,
    }))
)

function loadLegacyBusinessCategories() {
  try {
    const stored = JSON.parse(localStorage.getItem(BUSINESS_CATEGORY_STORAGE_KEY) || '[]')
    return Array.isArray(stored) ? stored.map(v => String(v).trim()).filter(Boolean) : []
  } catch {
    return []
  }
}

async function loadBusinessCategories() {
  const res = await executionApi.getProjectBusinessCategories()
  const dbValues = Array.isArray(res.data) ? res.data : []
  const legacyValues = loadLegacyBusinessCategories()
  const merged = [...new Set([...dbValues, ...legacyValues, ...DEFAULT_BUSINESS_CATEGORIES].map(v => String(v).trim()).filter(Boolean))]
  businessCategories.value = merged
  if (legacyValues.length > 0) {
    await saveBusinessCategories()
    localStorage.removeItem(BUSINESS_CATEGORY_STORAGE_KEY)
  }
}

async function saveBusinessCategories() {
  const res = await executionApi.saveProjectBusinessCategories(businessCategories.value)
  businessCategories.value = Array.isArray(res.data) ? res.data : businessCategories.value
}

function openBusinessCategoryModal() {
  businessCategoryDraft.value = ''
  businessCategoryModalOpen.value = true
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
  const res = await executionApi.downloadProjectsTemplate()
  saveBlob(res.data, '프로젝트리스트_수주_양식.xlsx')
}

async function handleExcelFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await executionApi.importProjectsExcel(formData)
    const { imported = 0, updated = 0, skipped = 0 } = res.data || {}
    message.success(`엑셀 업로드 완료: 신규 ${imported}건, 수정 ${updated}건, 제외 ${skipped}건`)
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '엑셀 업로드 중 오류가 발생했습니다.')
  } finally {
    importing.value = false
  }
}

async function addBusinessCategory() {
  const value = businessCategoryDraft.value.trim()
  if (!value) return
  if (!businessCategories.value.includes(value)) {
    businessCategories.value = [...businessCategories.value, value]
    try {
      await saveBusinessCategories()
    } catch (e) {
      message.error(e.response?.data?.detail || '사업구분 저장 중 오류가 발생했습니다.')
    }
  }
  businessCategoryDraft.value = ''
}

async function removeBusinessCategory(category) {
  businessCategories.value = businessCategories.value.filter(item => item !== category)
  if (form.business_category === category) form.business_category = undefined
  try {
    await saveBusinessCategories()
  } catch (e) {
    message.error(e.response?.data?.detail || '사업구분 저장 중 오류가 발생했습니다.')
  }
}

function splitNotes(notes) {
  const raw = notes || ''
  const idx = raw.indexOf(REQ_MARKER)
  if (idx < 0) return { memo: raw, req: {} }
  try { return { memo: raw.slice(0, idx), req: JSON.parse(raw.slice(idx + REQ_MARKER.length)) || {} } }
  catch { return { memo: raw, req: {} } }
}

function buildNotes() {
  const req = {
    business_division: form.business_division,
    team_name: form.team_name,
    business_category: form.business_category,
    spg: form.spg,
    sales_manager: form.sales_manager,
    execution_manager: form.execution_manager,
    collection_manager: form.collection_manager,
    revenue_type: form.revenue_type,
    work_type: form.work_type,
    collection_terms: form.collection_terms,
    warranty_period: form.warranty_period,
    special_relation: form.special_relation,
    employment_insurance: form.employment_insurance,
    industrial_accident_insurance: form.industrial_accident_insurance,
    ...Object.fromEntries(COST_NOTE_KEYS.map(key => [key, form[key] || ''])),
  }
  return `${form.notes || ''}${REQ_MARKER}${JSON.stringify(req)}`
}

function withRequirementMeta(item) {
  const { memo, req } = splitNotes(item.notes)
  const costMeta = mergeCostMeta(req, item)
  return {
    ...item,
    notes: memo,
    business_division: req.business_division || '',
    team_name: req.team_name || '',
    business_category: req.business_category || '',
    spg: req.spg || '',
    sales_manager: req.sales_manager || '',
    execution_manager: req.execution_manager || '',
    collection_manager: req.collection_manager || '',
    revenue_type: req.revenue_type || '',
    work_type: req.work_type || '',
    collection_terms: req.collection_terms || '',
    warranty_period: req.warranty_period || '',
    special_relation: req.special_relation || '',
    employment_insurance: Boolean(req.employment_insurance),
    industrial_accident_insurance: Boolean(req.industrial_accident_insurance),
    ...costMeta,
    ...calculateCostTotals({ ...item, ...costMeta }),
  }
}

function toPayload() {
  return {
    project_no: form.project_no,
    project_name: form.project_name,
    client_id: form.client_id,
    client_name: form.client_name,
    contract_form: form.contract_form,
    contract_type: form.contract_type,
    status: form.status,
    contract_amount: form.contract_amount,
    contract_rate: form.contract_rate,
    contract_start: form.contract_start,
    contract_end: form.contract_end,
    construct_start: form.construct_start,
    construct_end: form.construct_end,
    pm_employee_code: form.pm_employee_code,
    pm_name: form.pm_name,
    pm_dept: form.pm_dept,
    region: form.region,
    ...Object.fromEntries(COST_DB_AMOUNT_KEYS.map(key => [key, toNumber(form[key])])),
    notes: buildNotes(),
  }
}

function projectEditorState() {
  return JSON.stringify(toPayload())
}

function isProjectEditorDirty() {
  return drawerOpen.value && projectEditorSnapshot.value && projectEditorState() !== projectEditorSnapshot.value
}

function closeProjectEditor() {
  drawerOpen.value = false
  projectEditorSnapshot.value = ''
}

function confirmProjectEditorCancel() {
  if (projectCancelConfirmOpen.value) return
  projectCancelConfirmOpen.value = true
  Modal.confirm({
    title: '입력을 취소하시겠습니까?',
    content: '저장하지 않은 프로젝트 등록/수정 내용은 사라집니다.',
    okText: '입력 취소',
    cancelText: '계속 작성',
    okType: 'danger',
    onOk: closeProjectEditor,
    afterClose: () => {
      projectCancelConfirmOpen.value = false
    },
  })
}

function isProjectEditorPopupTarget(target) {
  return Boolean(target?.closest?.(
    '.project-editor-modal .ant-modal, ' +
    '.ant-modal-confirm, ' +
    '.ant-select-dropdown, ' +
    '.ant-picker-dropdown, ' +
    '.ant-dropdown, ' +
    '.ant-popover, ' +
    '.ant-tooltip'
  ))
}

function handleProjectEditorOutsideMouseDown(event) {
  if (!drawerOpen.value || isProjectEditorPopupTarget(event.target)) return
  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation?.()
  confirmProjectEditorCancel()
}

// 발주처 자동완성: 등록된 거래처 목록 제안 (직접 입력도 허용)
const clientSuggestions = computed(() => {
  const keyword = (form.client_name || '').toLowerCase()
  return companies.value
    .filter(c => !keyword || c.company_name.toLowerCase().includes(keyword))
    .map(c => ({ value: c.company_name, id: c.id }))
})

function onClientSelect(value, option) {
  // 목록에서 선택 시 client_id도 함께 설정
  form.client_id = option.id ?? null
}
function onClientChange(value) {
  // 직접 입력 시 client_id 초기화
  if (!value) { form.client_id = null; return }
  const match = companies.value.find(c => c.company_name === value)
  form.client_id = match ? match.id : null
}

function onContractStartChange(val) {
  if (val && !form.construct_start) form.construct_start = val
}

function onTeamChange(value) {
  const selected = teamOptions.value.find(option => option.value === value)
  if (selected?.rootName) {
    form.business_division = selected.rootName
  }
  if (!form.pm_dept && value) {
    form.pm_dept = value
  }
}

function onPmEmployeeChange(value, option) {
  const employee = option?.employee || employees.value.find(emp => emp.emp_code === value)
  if (!employee) {
    form.pm_employee_code = null
    form.pm_name = ''
    return
  }
  form.pm_employee_code = employee.emp_code
  form.pm_name = employee.name
  if (employee.department_name) form.pm_dept = employee.department_name
}

function findUniqueEmployeeCodeByName(name) {
  const value = String(name || '').trim()
  if (!value) return null
  const matches = employees.value.filter(emp => emp.name === value)
  return matches.length === 1 ? matches[0].emp_code : null
}

function openDrawer(item) {
  editItem.value = item
  const { memo, req } = splitNotes(item?.notes)
  Object.assign(form, item ? {
    project_no:      item.project_no     ?? '',
    project_name:    item.project_name,
    client_id:       item.client_id      ?? null,
    client_name:     item.client_name    ?? '',
    contract_form:   item.contract_form  ?? '원도급',
    contract_type:   item.contract_type  ?? '국내',
    status:          item.status         ?? '미진행',
    contract_amount: item.contract_amount ?? 0,
    contract_rate:   item.contract_rate   ?? 0,
    contract_start:  item.contract_start  ?? null,
    contract_end:    item.contract_end    ?? null,
    construct_start: item.construct_start ?? null,
    construct_end:   item.construct_end   ?? null,
    pm_employee_code: item.pm_employee_code ?? findUniqueEmployeeCodeByName(item.pm_name),
    pm_name:         item.pm_name ?? '',
    pm_dept:         item.pm_dept ?? '',
    region:          item.region  ?? '',
    notes:           memo ?? '',
    business_division: req.business_division || undefined,
    team_name: req.team_name || '',
    business_category: req.business_category || undefined,
    spg: req.spg || undefined,
    sales_manager: req.sales_manager || '',
    execution_manager: req.execution_manager || '',
    collection_manager: req.collection_manager || '',
    revenue_type: req.revenue_type || undefined,
    work_type: req.work_type || undefined,
    collection_terms: req.collection_terms || '',
    warranty_period: req.warranty_period || '',
    special_relation: req.special_relation || 'x',
    employment_insurance: Boolean(req.employment_insurance),
    industrial_accident_insurance: Boolean(req.industrial_accident_insurance),
    ...mergeCostMeta(req, item),
  } : emptyForm)
  projectEditorSnapshot.value = projectEditorState()
  drawerOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await executionApi.updateProject(editItem.value.id, toPayload())
      message.success('수정되었습니다.')
    } else {
      await executionApi.createProject(toPayload())
      message.success('등록되었습니다.')
    }
    closeProjectEditor()
    await load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await executionApi.deleteProject(id)
    if (selectedId.value === id) selectedId.value = null
    message.success('삭제되었습니다.')
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

async function load() {
  loading.value = true
  try {
    const [proj, co, dept, emp, recv, salesPlan, previousSalesPlan, purchasePlan, previousPurchasePlan] = await Promise.all([
      executionApi.getProjects(),
      masterApi.getCompanies(),
      masterApi.getDepartments({ org_year: orgYear, include_inactive: false, tree: true }),
      masterApi.getEmployees(),
      managementApi.getReceivables(),
      executionApi.getProjectSalesPlans(orgYear),
      executionApi.getProjectSalesPlans(orgYear - 1),
      executionApi.getProjectPurchasePlans(orgYear),
      executionApi.getProjectPurchasePlans(orgYear - 1),
      loadBusinessCategories(),
    ])
    items.value     = proj.data.map(withRequirementMeta)
    companies.value = co.data
    departments.value = dept.data || []
    employees.value = emp.data || []
    receivables.value = recv.data?.items || []
    salesPlanRows.value = (salesPlan.data || []).map(normalizeSalesPlanRow)
    previousSalesPlanRows.value = (previousSalesPlan.data || []).map(normalizeSalesPlanRow)
    purchasePlanRows.value = (purchasePlan.data || []).map(normalizePurchasePlanRow)
    previousPurchasePlanRows.value = (previousPurchasePlan.data || []).map(normalizePurchasePlanRow)
    syncSalesPlanRowsWithProjects({ silent: true })
    syncPurchasePlanRowsWithProjects({ silent: true })
  } finally {
    loading.value = false
  }
}

onMounted(load)

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleProjectEditorOutsideMouseDown, true)
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.tab-content { display: flex; flex-direction: column; gap: 16px; }
.project-tabs :deep(.ant-tabs-nav) { margin: 0 0 16px; }
.project-tabs :deep(.ant-tabs-tab) { font-weight: 600; }

/* ── 통계 카드 ── */
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; }
.stat-green  { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-icon   { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-gray   { background: #f0f2f5; color: #595959; }
.icon-blue   { background: #e6f4ff; color: #1677ff; }
.icon-green  { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

/* ── 검색 조건 ── */
.filter-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.filter-table { width: 100%; border-collapse: collapse; }
.filter-table th {
  width: 90px; padding: 8px 12px; background: #fafafa;
  font-size: 12px; font-weight: 600; color: #595959;
  border: 1px solid #f0f0f0; white-space: nowrap; text-align: center;
}
.filter-table td { padding: 8px 12px; border: 1px solid #f0f0f0; }
.filter-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 8px; border-top: 1px solid #f5f5f5;
}
.filter-count { font-size: 13px; color: #595959; }
.filter-count b { color: #1677ff; }

/* ── 테이블 카드 ── */
.table-card  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }

/* ── 테이블 행 ── */
:deep(.proj-row) { cursor: pointer; transition: background 0.15s; }
:deep(.proj-row:hover td) { background: #f0f7ff !important; }
:deep(.proj-row--selected td) { background: #e6f4ff !important; }
:deep(.proj-row--overdue td) { background: #fff7e6 !important; }

.name-cell    { display: flex; align-items: center; }
.name-selected { font-weight: 600; color: #1677ff; }
.num-cell     { font-variant-numeric: tabular-nums; }
.overdue-mark { color: #fa8c16; margin-left: 4px; font-size: 13px; }
.del-link     { color: #e74c3c; }
.del-link:hover { color: #c0392b; }
.category-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.category-tags :deep(.ant-tag) { margin-inline-end: 0; padding: 4px 8px; }
.detail-cost-table { width: 100%; border-collapse: collapse; margin-bottom: 14px; table-layout: fixed; }
.detail-cost-table th,
.detail-cost-table td { border: 1px solid #d9d9d9; padding: 5px 7px; text-align: center; font-size: 12px; vertical-align: middle; }
.detail-cost-table thead th { background: #203f70; color: #fff; font-weight: 700; }
.detail-cost-table .group-cell { background: #f0f0f0; color: #111; font-weight: 700; }
.detail-cost-table .item-cell { background: #fafafa; font-weight: 600; }
.detail-cost-table .summary-row td { background: #f3f3f3; font-weight: 700; }
.detail-cost-table .profit-row td { background: #eef4ff; color: #163b73; font-weight: 700; }
.detail-cost-table :deep(.ant-input-number) { width: 100%; }
.detail-cost-table .note-col,
.detail-cost-table .note-cell { width: 120px; }
.detail-cost-table .note-cell :deep(.ant-input) { width: 100%; min-width: 0; }
.readonly-amount,
.ratio-cell { font-variant-numeric: tabular-nums; text-align: right !important; }

/* ── Drawer 섹션 ── */
.sec-label { font-size: 12px; color: #8c8c8c; font-weight: 500; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
