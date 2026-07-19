import { Layout, Menu } from 'antd';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import StrategyConfig from './pages/StrategyConfig';
import BacktestResult from './pages/BacktestResult';
import StrategyList from './pages/StrategyList';
import FactorLibrary from './pages/FactorLibrary';
import SupportLevel from './pages/SupportLevel';

const { Header, Content } = Layout;

function App() {
  const menuItems = [
    { key: 'config', label: <Link to="/">策略配置</Link> },
    { key: 'list', label: <Link to="/strategies">策略列表</Link> },
    { key: 'factors', label: <Link to="/factors">因子库</Link> },
    { key: 'support', label: <Link to="/support-level">支撑位分析</Link> },
  ];

  return (
    <BrowserRouter>
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ color: '#fff', fontSize: 18, fontWeight: 'bold', marginRight: 48 }}>
            量化回测系统
          </div>
          <Menu theme="dark" mode="horizontal" items={menuItems} style={{ flex: 1 }} />
        </Header>
        <Content>
          <Routes>
            <Route path="/" element={<StrategyConfig />} />
            <Route path="/result/:id" element={<BacktestResult />} />
            <Route path="/strategies" element={<StrategyList />} />
            <Route path="/factors" element={<FactorLibrary />} />
            <Route path="/support-level" element={<SupportLevel />} />
          </Routes>
        </Content>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
