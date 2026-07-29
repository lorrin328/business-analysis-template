# 证保网点参考表

实际名单文件为 `证保网点参考表.csv`，属于内部网点主数据，不进入公开 GitHub。

当前确认口径：

- 常规网点：参数表 AA2—AA148，共147个，纳入常规网点数和活动率分母。
- 转介绍网点：参数表 AA151—AA237中的86个有效网点，归属于“广发证券股份有限公司”，不纳入常规网点数。
- 参考表不保存顾问专员、更新人、人员姓名或工号。

源工作簿参数表更新后，先在本地重新生成：

```powershell
python scripts/build_branch_reference.py `
  --source "<含参数表的证保业务报表.xlsx>" `
  --output "data\reference\证保网点参考表.csv"
```

生产导入使用受保护的运行数据库：

```bash
sudo -u www-data BUSINESS_ANALYSIS_DB=/var/lib/business-analysis/business_data.db \
  /opt/business-analysis/backend/venv/bin/python \
  /opt/business-analysis/backend/import_branch_reference.py \
  --source /path/to/证保网点参考表.csv
```

导入程序会强校验147个常规网点、86个转介绍网点、参考编号唯一和网点名称唯一；任一条件不满足时整批回滚。
