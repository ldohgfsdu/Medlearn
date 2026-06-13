# 邮箱验证码注册配置

客户端注册流程使用 Supabase Auth 的 `signUp`、`verifyOtp` 和 `resend`。
要让确认邮件显示 6 位验证码，需要在 Supabase Dashboard 完成以下配置。

## 1. 开启邮箱确认

进入 `Authentication -> Providers -> Email`：

- 开启 Email Provider。
- 开启 Confirm email。
- 保持 Secure email change 开启。

## 2. 修改注册邮件模板

进入 `Authentication -> Email Templates -> Confirm signup`，把确认链接模板改为验证码模板。

示例正文：

```html
<h2>欢迎注册 Medlearn</h2>
<p>您的邮箱验证码是：</p>
<p style="font-size: 32px; font-weight: 700; letter-spacing: 8px;">
  {{ .Token }}
</p>
<p>验证码将在短时间后失效。请勿将验证码转发给他人。</p>
```

关键点是使用 `{{ .Token }}`，不要只保留 `{{ .ConfirmationURL }}`。

## 3. 配置发件服务

开发阶段可使用 Supabase 内置邮件服务，但它有较严格的频率限制。
正式环境应在 `Project Settings -> Authentication -> SMTP Settings` 配置自有 SMTP，
并设置品牌化的发件人名称、地址和回复地址。

## 4. 安全建议

- 保留 Supabase 的发送频率限制。
- 客户端重发按钮至少倒计时 60 秒。
- 不在日志中记录验证码、密码或完整访问令牌。
- 上线前测试验证码过期、重复发送、已注册邮箱和弱网络场景。
