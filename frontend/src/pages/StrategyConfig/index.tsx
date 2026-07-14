import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Slider,
  Space,
  message,
} from 'antd';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;
import { backtestApi, dataApi, factorApi } from '../../services/api';
import type { CustomFactor, FactorInfo, SymbolInfo } from '../../types';

const { Option } = Select;
const { TextArea } = Input;

const intervals = [
  { value: '1h', label: '1小时' },
  { value: '4h', label: '4小时' },
  { value: '1d', label: '1天' },
];

const marketTypes = [
  { value: 'spot', label: '现货' },
  { value: 'futures_usdt', label: 'USDT 合约' },
];

const positionModes = [
  { value: 'fixed_ratio', label: '固定比例' },
  { value: 'fixed_amount', label: '固定金额' },
];

export default function StrategyConfig() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [factors, setFactors] = useState<FactorInfo[]>([]);
  const [customFactors, setCustomFactors] = useState<CustomFactor[]>([]);
  const [loadingSymbols, setLoadingSymbols] = useState(false);
  const [running, setRunning] = useState(false);
  const [factorMode, setFactorMode] = useState<'formula' | 'python'>('formula');

  useEffect(() => {
    loadSymbols();
    loadFactors();
  }, []);

  const loadSymbols = async () => {
    setLoadingSymbols(true);
    try {
      const data = await dataApi.getSymbols('spot');
      setSymbols(data.slice(0, 100));
    } catch (err) {
      message.error('获取交易对失败');
    } finally {
      setLoadingSymbols(false);
    }
  };

  const loadFactors = async () => {
    try {
      const [builtins, customs] = await Promise.all([
        factorApi.getBuiltins(),
        factorApi.getCustomFactors(),
      ]);
      setFactors(builtins);
      setCustomFactors(customs);
    } catch (err) {
      message.error('获取因子失败');
    }
  };

  const handleInsertFactor = (signature: string) => {
    const current = form.getFieldValue('factor_expression') || '';
    form.setFieldsValue({ factor_expression: current ? `${current} ${signature}` : signature });
  };

  const handleInsertCustomFactor = (factorId: string) => {
    const factor = customFactors.find((f) => f.id === factorId);
    if (!factor) return;

    if (factor.mode === 'formula') {
      form.setFieldsValue({ factor_expression: factor.code });
    } else {
      form.setFieldsValue({ factor_code: factor.code });
    }
  };

  const filteredCustomFactors = customFactors.filter((f) => f.mode === factorMode);

  const handleRun = async (values: any) => {
    setRunning(true);
    try {
      const fromDate = values.date_range[0].format('YYYY-MM-DD');
      const toDate = values.date_range[1].format('YYYY-MM-DD');

      const strategy = {
        name: values.name,
        factor_mode: values.factor_mode,
        factor_expression: values.factor_expression,
        factor_code: values.factor_code,
        position_mode: values.position_mode,
        position_ratio: values.position_ratio,
        initial_capital: values.initial_capital,
        fee_rate: values.fee_rate,
        slippage: values.slippage,
        stop_loss: values.stop_loss,
        take_profit: values.take_profit,
        max_holding_bars: values.max_holding_bars,
      };

      const data = {
        symbol: values.symbol,
        interval: values.interval,
        market_type: values.market_type,
        from: fromDate,
        to: toDate,
      };

      const result = await backtestApi.runBacktest({ strategy, data });
      message.success('回测完成');
      navigate(`/result/${result.id}`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '回测失败');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1>策略配置</h1>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleRun}
        initialValues={{
          name: '双均线金叉策略',
          symbol: 'BTC_USDT',
          market_type: 'spot',
          interval: '4h',
          factor_mode: 'formula',
          factor_expression: "AND(EMA(close, 12) > EMA(close, 26), RSI(close, 14) < 70)",
          factor_code: "def factor(df):\n    momentum = df['close'].pct_change(10)\n    return momentum\n",
          position_mode: 'fixed_ratio',
          position_ratio: 0.95,
          initial_capital: 10000,
          fee_rate: 0.002,
          slippage: 0.0005,
          stop_loss: 0,
          take_profit: 0,
          max_holding_bars: 0,
          date_range: [dayjs().subtract(3, 'month'), dayjs()],
        }}
      >
        <Card title="基本信息" style={{ marginBottom: 24 }}>
          <Form.Item label="策略名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Card>

        <Card title="交易设置" style={{ marginBottom: 24 }}>
          <Space style={{ display: 'flex', flexWrap: 'wrap' }}>
            <Form.Item label="交易对" name="symbol" rules={[{ required: true }]}>
              <Select
                showSearch
                style={{ width: 200 }}
                loading={loadingSymbols}
                filterOption={(input, option) =>
                  (option?.value as string).toLowerCase().includes(input.toLowerCase())
                }
              >
                {symbols.map((s) => (
                  <Option key={s.symbol} value={s.symbol}>
                    {s.symbol}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item label="市场类型" name="market_type" rules={[{ required: true }]}>
              <Select style={{ width: 160 }}>
                {marketTypes.map((m) => (
                  <Option key={m.value} value={m.value}>
                    {m.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item label="周期" name="interval" rules={[{ required: true }]}>
              <Select style={{ width: 120 }}>
                {intervals.map((i) => (
                  <Option key={i.value} value={i.value}>
                    {i.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Space>
        </Card>

        <Card title="数据范围" style={{ marginBottom: 24 }}>
          <Form.Item label="时间范围" name="date_range" rules={[{ required: true }]}>
            <RangePicker style={{ width: 320 }} />
          </Form.Item>
        </Card>

        <Card title="因子输入" style={{ marginBottom: 24 }}>
          <Form.Item label="输入模式" name="factor_mode">
            <Radio.Group onChange={(e) => setFactorMode(e.target.value)}>
              <Radio value="formula">公式表达式</Radio>
              <Radio value="python">Python 代码</Radio>
            </Radio.Group>
          </Form.Item>

          {factorMode === 'formula' && (
            <>
              <Form.Item label="因子公式" name="factor_expression" rules={[{ required: true }]}>
                <TextArea rows={4} placeholder="例如：AND(EMA(close, 12) > EMA(close, 26), RSI(close, 14) < 70)" />
              </Form.Item>
              <Form.Item label="快速插入内置因子">
                <Select
                  placeholder="选择因子"
                  style={{ width: 280 }}
                  onChange={handleInsertFactor}
                  options={factors.map((f) => ({
                    value: f.signature,
                    label: `${f.name} - ${f.description}`,
                  }))}
                />
              </Form.Item>
              {filteredCustomFactors.length > 0 && (
                <Form.Item label="插入自定义公式因子">
                  <Select
                    placeholder="选择自定义因子"
                    style={{ width: 280 }}
                    onChange={handleInsertCustomFactor}
                    allowClear
                    options={filteredCustomFactors.map((f) => ({
                      value: f.id,
                      label: `${f.name}${f.description ? ` - ${f.description}` : ''}`,
                    }))}
                  />
                </Form.Item>
              )}
            </>
          )}

          {factorMode === 'python' && (
            <>
              <Form.Item label="Python 代码" name="factor_code" rules={[{ required: true }]}>
                <TextArea rows={10} placeholder="def factor(df): ..." />
              </Form.Item>
              {filteredCustomFactors.length > 0 && (
                <Form.Item label="插入自定义 Python 因子">
                  <Select
                    placeholder="选择自定义因子"
                    style={{ width: 280 }}
                    onChange={handleInsertCustomFactor}
                    allowClear
                    options={filteredCustomFactors.map((f) => ({
                      value: f.id,
                      label: `${f.name}${f.description ? ` - ${f.description}` : ''}`,
                    }))}
                  />
                </Form.Item>
              )}
            </>
          )}
        </Card>

        <Card title="回测参数" style={{ marginBottom: 24 }}>
          <Space style={{ display: 'flex', flexWrap: 'wrap' }} align="start">
            <Form.Item label="仓位模式" name="position_mode" rules={[{ required: true }]}>
              <Select style={{ width: 160 }}>
                {positionModes.map((p) => (
                  <Option key={p.value} value={p.value}>
                    {p.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item label="仓位比例" name="position_ratio" rules={[{ required: true }]}>
              <Slider style={{ width: 200 }} min={0} max={1} step={0.05} />
            </Form.Item>

            <Form.Item label="初始资金" name="initial_capital" rules={[{ required: true }]}>
              <InputNumber style={{ width: 160 }} min={100} step={1000} />
            </Form.Item>

            <Form.Item label="手续费率" name="fee_rate" rules={[{ required: true }]}>
              <InputNumber style={{ width: 160 }} min={0} step={0.0001} />
            </Form.Item>

            <Form.Item label="滑点" name="slippage" rules={[{ required: true }]}>
              <InputNumber style={{ width: 160 }} min={0} step={0.0001} />
            </Form.Item>

            <Form.Item label="止损比例" name="stop_loss" rules={[{ required: true }]}>
              <InputNumber
                style={{ width: 160 }}
                min={0}
                max={1}
                step={0.01}
                formatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
                parser={(value) => value?.replace('%', '') ? Number(value?.replace('%', '')) / 100 : 0}
              />
            </Form.Item>

            <Form.Item label="止盈比例" name="take_profit" rules={[{ required: true }]}>
              <InputNumber
                style={{ width: 160 }}
                min={0}
                max={10}
                step={0.01}
                formatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
                parser={(value) => value?.replace('%', '') ? Number(value?.replace('%', '')) / 100 : 0}
              />
            </Form.Item>

            <Form.Item label="最大持仓(K线数)" name="max_holding_bars" rules={[{ required: true }]}>
              <InputNumber style={{ width: 160 }} min={0} step={1} precision={0} />
            </Form.Item>
          </Space>
        </Card>

        <Form.Item>
          <Button type="primary" htmlType="submit" size="large" loading={running}>
            运行回测
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
