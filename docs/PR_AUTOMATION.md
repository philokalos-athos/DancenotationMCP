# PR / Merge Automation 权限配置

## 让代理可以“直接提交 PR”需要的最小权限

1. **代码仓库写权限**
   - 机器人账号（或 GitHub App）至少要有仓库 `Contents: Read and write`。
2. **Pull Requests 权限**
   - 至少 `Pull requests: Read and write`，用于创建/更新 PR。
3. **Workflows（可选）**
   - 若代理需要触发 CI、自动修复后重跑流水线，给 `Actions: Read and write`。
4. **分支保护例外（视策略）**
   - 若默认分支有强保护（必须 review / 必须状态检查），代理要么：
     - 仅创建 PR 不直接 merge；或
     - 被加入允许 bypass 的角色/应用。

## 让代理可以“直接 merge”还需要

1. 满足分支保护规则（review、checks、线性历史等）。
2. 代理身份具备 `Maintain` / `Admin` 或 branch rule 中明确允许 `bypass`。
3. 如启用了 CODEOWNERS，代理需满足 Code Owners 审批策略，除非规则允许绕过。

## 建议的安全配置

- 代理默认只做：`push branch + create PR`。
- merge 交给：
  - 自动合并（GitHub Auto-merge，条件通过后自动合并）；或
  - 受控管理员审批后合并。

## 在本地 CLI 中常用的认证方式

- `gh auth login`（PAT 或设备登录）
- 令牌权限建议至少包含：`repo`（私有仓库），若要管理工作流再加 `workflow`。

## 冲突修复常规流程（给人/代理都适用）

```bash
git fetch origin
git checkout <feature-branch>
git merge origin/<base-branch>
# 解决冲突后
git add <resolved-files>
git commit -m "Resolve merge conflicts with <base-branch>"
git push
```

若你提供可访问的 remote（当前环境对 GitHub 出网被 403），代理即可直接执行上面的完整流程。
