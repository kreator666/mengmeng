import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  List,
  Radio,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { factorApi } from '../../services/api';
import markethonApi from '../../services/markethonApi';
import type { CustomFactor, FactorInfo } from '../../types';
import type {
  MarkethonBuiltinMapping,
  MarkethonDefineFactorItem,
  MarkethonFactorMapItem,
  MarkethonStatusResponse,
} from '../../types/markethon';

const { Text, Title } = Typography;
const { Option } = Select;
const { Panel } = Collapse;

const COMPETITION_START = '2021-08-21';
const COMPETITION_END = '2026-08-20';
// 天梯官方 IM 股票池训练预热起点，与 design/submit_leaderboard_demo.py 一致。
const DATA_LOAD_START = '2020-08-21';

interface ProjectFactor {
  id: string;
  name: string;
  mode: 'formula' | 'python';
  category: string;
  description: string;
  code?: string;
}

interface FactorMappingRow {
  projectFactor: ProjectFactor;
  expression: string;
  markethonName: string;
  savedMap?: MarkethonFactorMapItem;
}

const BENCHMARKS = [
  { value: 'IC', label: '中证 500 (IC)' },
  { value: 'IF', label: '沪深 300 (IF)' },
  { value: 'IH', label: '上证 50 (IH)' },
  { value: 'IM', label: '中证 1000 (IM)' },
];

export default function Competition() {
  const [loginForm] = Form.useForm();
  const [loadForm] = Form.useForm();
  const [strategyForm] = Form.useForm();

  const [loggedIn, setLoggedIn] = useState(false);
  const [status, setStatus] = useState<MarkethonStatusResponse | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  const [projectFactors, setProjectFactors] = useState<ProjectFactor[]>([]);
  const [builtinMappings, setBuiltinMappings] = useState<Record<string, MarkethonBuiltinMapping>>({});
  const [savedMaps, setSavedMaps] = useState<MarkethonFactorMapItem[]>([]);
  const [mappingRows, setMappingRows] = useState<Record<string, FactorMappingRow>>({});
  const [selectedFactorIds, setSelectedFactorIds] = useState<string[]>([]);
  const [registeredMarkethonFactors, setRegisteredMarkethonFactors] = useState<string[]>([]);

  const [activeTab, setActiveTab] = useState('metrics');
  const [result, setResult] = useState<any>(null);
  const [runningAction, setRunningAction] = useState<string | null>(null);

  // 加载项目因子库与映射
  useEffect(() => {
    loadProjectFactors();
    loadBuiltinMappings();
    loadSavedMaps();
  }, []);

  const loadProjectFactors = async () => {
    try {
      const library = await factorApi.getFactorLibrary();
      const builtins: ProjectFactor[] = (library.builtins || []).map((f: FactorInfo) => ({
        id: f.name,
        name: f.name,
        mode: 'formula',
        category: f.category,
        description: f.description,
      }));
      const customs: ProjectFactor[] = (library.custom || []).map((f: CustomFactor) => ({
        id: f.id,
        name: f.name,
        mode: f.mode as 'formula' | 'python',
        category: f.category,
        description: f.description,
        code: f.code,
      }));
      setProjectFactors([...builtins, ...customs]);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '获取项目因子库失败');
    }
  };

  const loadBuiltinMappings = async () => {
    try {
      const data = await markethonApi.getBuiltinMappings();
      setBuiltinMappings(data.mappings || {});
    } catch (err: any) {
      message.error(err.response?.data?.detail || '获取内置映射建议失败');
    }
  };

  const loadSavedMaps = async () => {
    try {
      const maps = await markethonApi.listFactorMaps();
      setSavedMaps(maps);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '获取已保存映射失败');
    }
  };

  // 当项目因子或保存映射变化时，构建映射行
  useEffect(() => {
    const rows: Record<string, FactorMappingRow> = {};
    projectFactors.forEach((pf) => {
      const saved = savedMaps.find((m) => m.project_factor_id === pf.id);
      let expression = saved?.qlib_expression || '';
      let markethonName = saved?.markethon_name || '';

      if (!expression && builtinMappings[pf.name]?.supported) {
        expression = builtinMappings[pf.name].example || '';
        markethonName = `${pf.name}_MKT`;
      }
      if (!markethonName) {
        markethonName = `${pf.name}_MKT`;
      }

      rows[pf.id] = {
        projectFactor: pf,
        expression,
        markethonName,
        savedMap: saved,
      };
    });
    setMappingRows(rows);
  }, [projectFactors, savedMaps, builtinMappings]);

  const refreshStatus = async () => {
    setLoadingStatus(true);
    try {
      const data = await markethonApi.getStatus();
      setStatus(data);
      setLoggedIn(true);
    } catch (err: any) {
      setStatus(null);
      setLoggedIn(false);
      message.error(err.response?.data?.detail || '获取 Markethon 状态失败，可能需要先登录');
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleLogin = async (values: { username: string; password: string }) => {
    try {
      await markethonApi.login(values);
      message.success('登录成功');
      setLoggedIn(true);
      await refreshStatus();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '登录失败');
    }
  };

  const handleLoadData = async (values: { limit: number; alpha360: boolean; universe?: string }) => {
    if (values.limit < 500 && !values.universe) {
      message.error('按 limit 加载时股票数量不少于 500 只');
      return;
    }
    setLoadingData(true);
    try {
      await markethonApi.loadData({
        limit: values.limit,
        start: DATA_LOAD_START,
        end: COMPETITION_END,
        alpha360: values.alpha360,
        universe: values.universe,
      });
      message.success('数据加载完成');
      await refreshStatus();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '数据加载失败');
    } finally {
      setLoadingData(false);
    }
  };

  const updateMappingRow = (id: string, updates: Partial<FactorMappingRow>) => {
    setMappingRows((prev) => ({
      ...prev,
      [id]: { ...prev[id], ...updates },
    }));
  };

  const handleUseSuggestion = (pf: ProjectFactor) => {
    const suggestion = builtinMappings[pf.name];
    if (suggestion?.supported && suggestion.example) {
      updateMappingRow(pf.id, { expression: suggestion.example });
      message.info(`已填充 ${pf.name} 建议表达式`);
    }
  };

  const handleRegisterSingle = async (row: FactorMappingRow) => {
    if (!row.expression.trim()) {
      message.error('qlib 表达式不能为空');
      return;
    }
    try {
      await markethonApi.defineFactor({
        name: row.markethonName,
        expression: row.expression,
      });
      await markethonApi.saveFactorMap({
        project_factor_id: row.projectFactor.id,
        project_factor_name: row.projectFactor.name,
        project_factor_mode: row.projectFactor.mode,
        qlib_expression: row.expression,
        markethon_name: row.markethonName,
      });
      message.success(`因子 ${row.markethonName} 注册成功`);
      await loadSavedMaps();
      await refreshMarkethonFactors();
    } catch (err: any) {
      message.error(err.response?.data?.detail || `注册 ${row.markethonName} 失败`);
    }
  };

  const handleBatchRegister = async () => {
    const selectedRows = selectedFactorIds.map((id) => mappingRows[id]).filter(Boolean);
    const invalid = selectedRows.find((r) => !r.expression.trim());
    if (invalid) {
      message.error(`请为 ${invalid.projectFactor.name} 填写 qlib 表达式`);
      return;
    }

    const factors: MarkethonDefineFactorItem[] = selectedRows.map((r) => ({
      name: r.markethonName,
      expression: r.expression,
    }));

    try {
      const res = await markethonApi.defineFactorsBatch({ factors, save_maps: true });
      const failed = res.results.filter((r) => !r.ok);
      if (failed.length > 0) {
        message.warning(`批量注册完成：${res.successes} 成功，${res.failures} 失败`);
      } else {
        message.success(`批量注册完成：${res.successes} 个因子`);
      }
      // 保存映射
      for (const row of selectedRows) {
        try {
          await markethonApi.saveFactorMap({
            project_factor_id: row.projectFactor.id,
            project_factor_name: row.projectFactor.name,
            project_factor_mode: row.projectFactor.mode,
            qlib_expression: row.expression,
            markethon_name: row.markethonName,
          });
        } catch {
          // ignore duplicate save errors
        }
      }
      await loadSavedMaps();
      await refreshMarkethonFactors();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '批量注册失败');
    }
  };

  const refreshMarkethonFactors = async () => {
    try {
      const data = await markethonApi.listFactors();
      const all = [
        ...(data.alpha158 || []),
        ...(data.alpha360 || []),
        ...Object.keys(data.custom || {}),
      ];
      setRegisteredMarkethonFactors(all);
    } catch {
      setRegisteredMarkethonFactors([]);
    }
  };

  useEffect(() => {
    if (loggedIn) {
      refreshMarkethonFactors();
    }
  }, [loggedIn]);

  const availableMarkethonFactorOptions = useMemo(() => {
    return registeredMarkethonFactors.map((name) => ({ value: name, label: name }));
  }, [registeredMarkethonFactors]);

  const handleEvaluate = async () => {
    const values = strategyForm.getFieldsValue();
    if (!values.names?.length) {
      message.error('请至少选择一个因子');
      return;
    }
    setRunningAction('evaluate');
    setActiveTab('factors');
    try {
      const data = await markethonApi.evaluateFactors({
        names: values.names,
        periods: values.periods || [1, 5, 10],
        quantiles: values.quantiles || 5,
        top_n: values.top_n || 50,
      });
      setResult({ type: 'evaluate', data });
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'IC 评估失败');
    } finally {
      setRunningAction(null);
    }
  };

  const handleBacktest = async () => {
    const values = strategyForm.getFieldsValue();
    if (!values.names?.length) {
      message.error('请至少选择一个因子');
      return;
    }
    setRunningAction('backtest');
    setActiveTab('backtest');
    try {
      const data = await markethonApi.backtestQuantile({
        names: values.names,
        weights: values.use_weights && values.weights ? values.weights : undefined,
        long_short: values.long_short,
        periods: values.periods_backtest || 5,
        quantiles: values.quantiles_backtest || 5,
        benchmark: values.long_short ? values.benchmark : undefined,
      });
      setResult({ type: 'backtest', data });
    } catch (err: any) {
      message.error(err.response?.data?.detail || '回测失败');
    } finally {
      setRunningAction(null);
    }
  };

  const handleSubmitLeaderboard = async () => {
    const values = strategyForm.getFieldsValue();
    if (!values.names?.length) {
      message.error('请至少选择一个因子');
      return;
    }
    setRunningAction('submit');
    setActiveTab('backtest');
    try {
      // 使用官方天梯提交端点 /scores/submit，参数由服务端强制固定。
      const data = await markethonApi.submitScore({
        names: values.names,
        submission_key: values.submission_key || `submit-${Date.now()}`,
        train_months: 12,
        test_months: 3,
        step_months: 3,
        long_short: true,
        quantiles: values.quantiles_backtest || 5,
        rebalance_periods: values.periods_backtest || 5,
        benchmark: 'IF',
        long_exposure: 0.95,
        short_exposure: 0.95,
        futures_cost: 0.0002,
        selection_method: values.selection_method || 'legacy',
        min_abs_icir: 0.10,
        min_abs_ic: 0.005,
        corr_threshold: 0.75,
        weight_shrinkage: 0.50,
        category_counts: null,
        uncategorized_count: values.names.length,
        submit_score: true,
      });
      setResult({ type: 'submit', data });
      const scoreInfo = data.standard_score;
      if (scoreInfo) {
        if (scoreInfo.eligible) {
          message.success(`天梯提交成功，标准分：${scoreInfo.score}`);
        } else {
          message.warning(`未满足天梯门槛：${scoreInfo.reason || '详见结果区'}`);
        }
      }
      if (data.submission_skipped) {
        message.warning('本次提交未计入天梯（未满足硬门槛）');
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '天梯提交失败');
    } finally {
      setRunningAction(null);
    }
  };

  const handleWalkForward = async () => {
    const values = strategyForm.getFieldsValue();
    if (!values.names?.length) {
      message.error('请至少选择一个因子');
      return;
    }
    setRunningAction('walk');
    setActiveTab('backtest');
    try {
      const data = await markethonApi.walkForward({
        names: values.names,
        train_months: 12,
        test_months: 3,
        step_months: 3,
        long_short: values.long_short,
        quantiles: values.quantiles_backtest || 5,
        rebalance_periods: values.periods_backtest || 5,
        selection_method: values.selection_method || 'legacy',
        benchmark: values.long_short ? values.benchmark : undefined,
        submit_score: false,
      });
      setResult({ type: 'walk_forward', data });
    } catch (err: any) {
      message.error(err.response?.data?.detail || '滚动验证失败');
    } finally {
      setRunningAction(null);
    }
  };

  const handleSelectStocks = async () => {
    const values = strategyForm.getFieldsValue();
    if (!values.names?.length) {
      message.error('请至少选择一个因子');
      return;
    }
    setRunningAction('select');
    setActiveTab('selection');
    try {
      const data = await markethonApi.selectStocks({
        names: values.names,
        weights: values.use_weights && values.weights ? values.weights : undefined,
        top_n: values.top_n_selection || 20,
        min_amount_cny: values.min_amount_cny || 0,
        min_listed_days: values.min_listed_days || 0,
      });
      setResult({ type: 'selection', data });
    } catch (err: any) {
      message.error(err.response?.data?.detail || '选股失败');
    } finally {
      setRunningAction(null);
    }
  };

  const mappingColumns: ColumnsType<ProjectFactor> = [
    {
      title: '选择',
      key: 'select',
      render: (_: any, record: ProjectFactor) => (
        <Checkbox
          checked={selectedFactorIds.includes(record.id)}
          onChange={(e) => {
            const checked = e.target.checked;
            setSelectedFactorIds((prev) =>
              checked ? [...prev, record.id] : prev.filter((id) => id !== record.id)
            );
          }}
        />
      ),
    },
    { title: '名称', dataIndex: 'name', key: 'name', render: (t: string) => <Tag>{t}</Tag> },
    { title: '模式', dataIndex: 'mode', key: 'mode' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: 'Markethon 因子名',
      key: 'markethonName',
      render: (_: any, record: ProjectFactor) => (
        <Input
          value={mappingRows[record.id]?.markethonName || ''}
          onChange={(e) => updateMappingRow(record.id, { markethonName: e.target.value })}
          style={{ width: 160 }}
        />
      ),
    },
    {
      title: 'qlib 表达式',
      key: 'expression',
      render: (_: any, record: ProjectFactor) => (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={mappingRows[record.id]?.expression || ''}
            onChange={(e) => updateMappingRow(record.id, { expression: e.target.value })}
            placeholder="例如：Mean($close, 20)"
            disabled={record.mode === 'python'}
          />
          {record.mode === 'python' && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Python 因子需手写等价的 qlib 表达式
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: '建议',
      key: 'suggestion',
      render: (_: any, record: ProjectFactor) => {
        const suggestion = builtinMappings[record.name];
        if (!suggestion) return <Text type="secondary">-</Text>;
        return (
          <Space>
            {suggestion.supported ? (
              <>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {suggestion.note}
                </Text>
                <Button size="small" onClick={() => handleUseSuggestion(record)}>
                  使用建议
                </Button>
              </>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {suggestion.note || '暂无建议'}
              </Text>
            )}
          </Space>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ProjectFactor) => (
        <Button size="small" type="primary" onClick={() => handleRegisterSingle(mappingRows[record.id])}>
          注册
        </Button>
      ),
    },
  ];

  const renderMetrics = (metrics: Record<string, any>) => {
    if (!metrics) return null;
    return (
      <Descriptions bordered column={3} size="small">
        {Object.entries(metrics).map(([key, value]) => (
          <Descriptions.Item key={key} label={key}>
            {typeof value === 'number' ? value.toFixed(4) : String(value)}
          </Descriptions.Item>
        ))}
      </Descriptions>
    );
  };

  const renderNavTable = (nav: Record<string, number | null>) => {
    if (!nav) return null;
    const entries = Object.entries(nav).slice(0, 20);
    const data = entries.map(([date, value]) => ({ date, value }));
    return (
      <Table
        dataSource={data}
        columns={[
          { title: '日期', dataIndex: 'date' },
          { title: '净值', dataIndex: 'value', render: (v: number | null) => (v === null ? '-' : v.toFixed(4)) },
        ]}
        pagination={false}
        size="small"
        rowKey="date"
      />
    );
  };

  const renderResult = () => {
    if (!result) {
      return <Alert message="请先执行 IC 评估、回测或选股" type="info" showIcon />;
    }

    switch (result.type) {
      case 'evaluate': {
        const factors = result.data?.factors || [];
        return (
          <Table
            dataSource={factors}
            columns={[
              { title: '因子', dataIndex: 'factor' },
              { title: 'IC均值', dataIndex: 'IC均值' },
              { title: 'ICIR', dataIndex: 'ICIR' },
              { title: 't统计量', dataIndex: 't统计量' },
              { title: 'IC>0占比', dataIndex: 'IC>0占比' },
              { title: '多空收益', dataIndex: '多空收益' },
            ]}
            rowKey="factor"
            size="small"
          />
        );
      }
      case 'backtest':
      case 'walk_forward':
      case 'submit': {
        const data = result.data;
        const scoreInfo = data.standard_score || {};
        return (
          <Space direction="vertical" style={{ width: '100%' }}>
            {scoreInfo.eligible !== undefined && (
              <Alert
                message={scoreInfo.eligible ? `天梯标准分：${scoreInfo.score}` : '未满足天梯门槛'}
                description={scoreInfo.reason || undefined}
                type={scoreInfo.eligible ? 'success' : 'warning'}
                showIcon
              />
            )}
            {result.type === 'submit' && data.submission && (
              <Alert message="成绩已成功提交到天梯" type="success" showIcon />
            )}
            {renderMetrics(data.metrics)}
            <Title level={5}>净值序列（前 20 条）</Title>
            {renderNavTable(data.nav)}
            {scoreInfo.coverage && (
              <Descriptions bordered size="small" title="覆盖率详情">
                <Descriptions.Item label="覆盖率">{(scoreInfo.coverage_ratio * 100).toFixed(2)}%</Descriptions.Item>
                <Descriptions.Item label="valid_days">{scoreInfo.coverage.valid_days}</Descriptions.Item>
                <Descriptions.Item label="leading_gap">{scoreInfo.coverage.leading_gap_days}</Descriptions.Item>
                <Descriptions.Item label="max_gap">{scoreInfo.coverage.max_gap_days}</Descriptions.Item>
              </Descriptions>
            )}
          </Space>
        );
      }
      case 'selection': {
        const data = result.data;
        return (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text strong>截面日期：{data.date}</Text>
            <Text type="secondary">过滤条件：{JSON.stringify(data.filters)}</Text>
            <Title level={5}>多头推荐</Title>
            <List
              dataSource={data.long_top || []}
              renderItem={(item: any) => (
                <List.Item>
                  <Text>
                    {item.symbol} | 评分：{item.score.toFixed(4)} | 收盘价：{item.close} | 成交额：
                    {item.amount_cny}
                  </Text>
                </List.Item>
              )}
            />
            <Title level={5}>空头警示</Title>
            <List
              dataSource={data.short_bottom || []}
              renderItem={(item: any) => (
                <List.Item>
                  <Text>
                    {item.symbol} | 评分：{item.score.toFixed(4)} | 收盘价：{item.close} | 成交额：
                    {item.amount_cny}
                  </Text>
                </List.Item>
              )}
            />
          </Space>
        );
      }
      default:
        return <pre>{JSON.stringify(result, null, 2)}</pre>;
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      <Title level={2}>比赛天梯</Title>
      <Alert
        message="天梯规则 v3（2026-08-21 起生效）"
        description={
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            <li>统一回测区间：{COMPETITION_START} 至 {COMPETITION_END}</li>
            <li>统一初始本金：人民币 1 亿元</li>
            <li>A 股按 100 股整手成交</li>
            <li>标准分权重：夏普 25%、年化收益 25%、年化 Alpha 20%、最大回撤 15%、回撤持续 15%</li>
          </ul>
        }
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* 账号与连接 */}
        <Card title="账号与连接">
          {!loggedIn ? (
            <Form form={loginForm} layout="inline" onFinish={handleLogin}>
              <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                <Input placeholder="用户名" style={{ width: 160 }} />
              </Form.Item>
              <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
                <Input.Password placeholder="密码" style={{ width: 160 }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit">
                  登录 / 注册
                </Button>
              </Form.Item>
            </Form>
          ) : (
            <Space>
              <Badge status="success" text="已登录" />
              <Button onClick={refreshStatus} loading={loadingStatus}>
                刷新状态
              </Button>
            </Space>
          )}

          {status && (
            <Descriptions bordered size="small" style={{ marginTop: 16 }}>
              <Descriptions.Item label="数据已加载">{status.loaded ? '是' : '否'}</Descriptions.Item>
              <Descriptions.Item label="股票数">{status.symbols ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="日期范围">
                {status.date_range ? `${status.date_range[0]} ~ ${status.date_range[1]}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Alpha158 因子数">{status.alpha158_factors ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="Alpha360 因子数">{status.alpha360_factors ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="自定义因子">{status.custom_factors?.join(', ') || '-'}</Descriptions.Item>
            </Descriptions>
          )}
        </Card>

        {/* 数据加载 */}
        <Card title="数据加载（天梯官方口径）">
          <Form form={loadForm} layout="inline" onFinish={handleLoadData} initialValues={{ limit: 0, alpha360: false, universe: 'IM' }}>
            <Form.Item label="评分区间" style={{ marginBottom: 0 }}>
              <Input value={`${COMPETITION_START} ~ ${COMPETITION_END}`} disabled style={{ width: 220 }} />
            </Form.Item>
            <Form.Item label="训练预热起点" style={{ marginBottom: 0 }}>
              <Input value={DATA_LOAD_START} disabled style={{ width: 130 }} />
            </Form.Item>
            <Form.Item name="universe" label="官方股票池">
              <Select style={{ width: 160 }}>
                <Option value="IM">中证 1000 (IM) — 官方</Option>
                <Option value="">按 limit 取前缀</Option>
                <Option value="IC">中证 500 (IC)</Option>
                <Option value="IF">沪深 300 (IF)</Option>
                <Option value="IH">上证 50 (IH)</Option>
                <Option value="IF+IC">IF+IC 合并</Option>
                <Option value="IC+IM">IC+IM 合并</Option>
              </Select>
            </Form.Item>
            <Form.Item name="limit" label="limit" rules={[{ required: true, type: 'number' }]}>
              <InputNumber min={0} style={{ width: 100 }} />
            </Form.Item>
            <Form.Item name="alpha360" label="Alpha360" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loadingData}>
                加载数据
              </Button>
            </Form.Item>
          </Form>
          <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
            提示：天梯官方股票池为 IM（中证 1000），训练预热起点 {DATA_LOAD_START}，评分固定区间 {COMPETITION_START} ~ {COMPETITION_END}。
          </Text>
        </Card>

        {/* 因子映射 */}
        <Card
          title="因子映射（复用项目现有因子）"
          extra={
            <Button type="primary" onClick={handleBatchRegister} disabled={selectedFactorIds.length === 0}>
              批量注册已勾选（{selectedFactorIds.length}）
            </Button>
          }
        >
          <Table
            dataSource={projectFactors}
            columns={mappingColumns}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            size="small"
            scroll={{ x: 1200 }}
          />
        </Card>

        {/* 策略配置 */}
        <Card title="策略配置">
          <Form
            form={strategyForm}
            layout="vertical"
            initialValues={{
              names: [],
              use_weights: false,
              weights: {},
              long_short: true,
              benchmark: 'IF',
              periods: [1, 5, 10],
              quantiles: 5,
              top_n: 50,
              periods_backtest: 5,
              quantiles_backtest: 5,
              train_months: 12,
              test_months: 3,
              step_months: 3,
              selection_method: 'legacy',
              top_n_selection: 20,
              min_amount_cny: 50000000,
              min_listed_days: 180,
              submission_key: '',
            }}
          >
            <Form.Item name="names" label="已注册 Markethon 因子" rules={[{ required: true }]}>
              <Select
                mode="multiple"
                placeholder="请选择已注册的 Markethon 因子"
                options={availableMarkethonFactorOptions}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Space style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item name="use_weights" valuePropName="checked" style={{ marginBottom: 0 }}>
                <Checkbox>使用自定义权重</Checkbox>
              </Form.Item>
              <Form.Item name="long_short" valuePropName="checked" style={{ marginBottom: 0 }}>
                <Checkbox>多空模式</Checkbox>
              </Form.Item>
            </Space>

            <Form.Item name="weights" label="因子权重（JSON 对象）" hidden={!strategyForm.getFieldValue('use_weights')}>
              <Input.TextArea rows={3} placeholder='{"KMID": 1, "ROC5": -1}' />
            </Form.Item>

            <Form.Item name="benchmark" label="空头指数">
              <Select style={{ width: 160 }}>
                {BENCHMARKS.map((b) => (
                  <Option key={b.value} value={b.value}>
                    {b.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="submission_key" label="天梯提交幂等键（留空则自动生成）">
              <Input placeholder="例如：darkspell-v1" style={{ width: 300 }} />
            </Form.Item>

            <Collapse ghost>
              <Panel header="高级参数" key="advanced">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Form.Item name="periods" label="IC 评估持有期">
                    <Select mode="tags" style={{ width: 240 }} tokenSeparators={[',']} />
                  </Form.Item>
                  <Form.Item name="quantiles" label="IC 评估分组数">
                    <InputNumber min={2} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="top_n" label="IC 评估返回条数">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="periods_backtest" label="回测调仓周期">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="quantiles_backtest" label="回测分组数">
                    <InputNumber min={2} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="train_months" label="训练窗口（月）">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="test_months" label="测试窗口（月）">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="step_months" label="滚动步长（月）">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="selection_method" label="选因子方式">
                    <Radio.Group>
                      <Radio value="legacy">legacy（按 |ICIR| 排序）</Radio>
                      <Radio value="robust">robust（稳定性筛选）</Radio>
                    </Radio.Group>
                  </Form.Item>
                  <Form.Item name="top_n_selection" label="选股返回数量">
                    <InputNumber min={1} style={{ width: 120 }} />
                  </Form.Item>
                  <Form.Item name="min_amount_cny" label="最低成交额">
                    <InputNumber min={0} style={{ width: 160 }} />
                  </Form.Item>
                  <Form.Item name="min_listed_days" label="最低上市天数">
                    <InputNumber min={0} style={{ width: 160 }} />
                  </Form.Item>
                </Space>
              </Panel>
            </Collapse>
          </Form>
        </Card>

        {/* 操作区 */}
        <Card title="操作">
          <Space wrap>
            <Button onClick={handleEvaluate} loading={runningAction === 'evaluate'}>
              IC 评估
            </Button>
            <Button onClick={handleBacktest} loading={runningAction === 'backtest'}>
              分组回测
            </Button>
            <Button type="primary" onClick={handleSubmitLeaderboard} loading={runningAction === 'submit'}>
              提交天梯成绩
            </Button>
            <Button onClick={handleWalkForward} loading={runningAction === 'walk'}>
              滚动验证（研究）
            </Button>
            <Button onClick={handleSelectStocks} loading={runningAction === 'select'}>
              选股
            </Button>
          </Space>
        </Card>

        {/* 结果展示 */}
        <Card title="结果">
          <Tabs activeKey={activeTab} onChange={setActiveTab}>
            <Tabs.TabPane tab="绩效/指标" key="metrics" />
            <Tabs.TabPane tab="因子评估" key="factors" />
            <Tabs.TabPane tab="回测/滚动" key="backtest" />
            <Tabs.TabPane tab="选股" key="selection" />
          </Tabs>
          {renderResult()}
        </Card>
      </Space>
    </div>
  );
}
