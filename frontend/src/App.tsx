import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Chat from "./pages/Chat";
import History from "./pages/History";
import Knowledge from "./pages/Knowledge";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#00E5FF",
          colorPrimaryBg: "rgba(0, 229, 255, 0.08)",
          colorPrimaryBgHover: "rgba(0, 229, 255, 0.15)",
          colorPrimaryBorder: "rgba(0, 229, 255, 0.3)",
          colorPrimaryHover: "#33EAFF",
          colorPrimaryActive: "#00B8D4",

          colorBgContainer: "#111633",
          colorBgElevated: "#181D3D",
          colorBgLayout: "#0A0E27",
          colorBgSpotlight: "#181D3D",
          colorBgMask: "rgba(0, 0, 0, 0.65)",

          colorText: "#E0E0E0",
          colorTextSecondary: "#8892A4",
          colorTextTertiary: "#5C6B82",
          colorTextQuaternary: "#3A4560",

          colorBorder: "rgba(255, 255, 255, 0.06)",
          colorBorderSecondary: "rgba(0, 229, 255, 0.08)",

          colorFill: "rgba(255, 255, 255, 0.04)",
          colorFillSecondary: "rgba(255, 255, 255, 0.06)",
          colorFillTertiary: "rgba(255, 255, 255, 0.02)",

          colorError: "#FF5252",
          colorSuccess: "#69F0AE",
          colorWarning: "#FFB74D",
          colorInfo: "#00E5FF",

          borderRadius: 2,
          borderRadiusLG: 4,
          borderRadiusSM: 2,
          borderRadiusXS: 1,

          fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif",
          fontSize: 14,
          lineHeight: 1.6,

          controlHeight: 36,
          controlHeightLG: 44,
          controlHeightSM: 28,

          boxShadow: "0 0 0 1px rgba(0, 229, 255, 0.06), 0 2px 24px rgba(0, 0, 0, 0.4)",
          boxShadowSecondary: "0 0 0 1px rgba(0, 229, 255, 0.04), 0 1px 12px rgba(0, 0, 0, 0.3)",
        },
        components: {
          Button: {
            borderRadius: 2,
            borderRadiusLG: 4,
            borderRadiusSM: 2,
            primaryShadow: "0 0 12px rgba(0, 229, 255, 0.2)",
          },
          Card: {
            borderRadiusLG: 4,
            paddingLG: 24,
          },
          Input: {
            activeShadow: "0 0 0 2px rgba(0, 229, 255, 0.15)",
            hoverBorderColor: "rgba(0, 229, 255, 0.3)",
            activeBorderColor: "#00E5FF",
          },
          Table: {
            headerBg: "rgba(0, 229, 255, 0.04)",
            headerColor: "#00E5FF",
            rowHoverBg: "rgba(0, 229, 255, 0.03)",
            borderColor: "rgba(255, 255, 255, 0.04)",
          },
          Menu: {
            darkItemBg: "transparent",
            darkItemHoverBg: "rgba(0, 229, 255, 0.08)",
            darkItemSelectedBg: "rgba(0, 229, 255, 0.12)",
            itemBorderRadius: 2,
          },
          Tag: {
            defaultBg: "rgba(0, 229, 255, 0.08)",
            defaultColor: "#00E5FF",
          },
          Statistic: {
            contentFontSize: 28,
            titleFontSize: 13,
          },
          Spin: {
            colorPrimary: "#00E5FF",
            dotSize: 32,
          },
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route element={<Layout />}>
              <Route path="/chat/:sessionId?" element={<Chat />} />
              <Route path="/history" element={<History />} />
              <Route path="/knowledge" element={<Knowledge />} />
              <Route path="/admin" element={<Admin />} />
            </Route>
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
