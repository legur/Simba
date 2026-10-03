---
id: AR-20260422-597
title: prompts.chat — PowerShell Script for Managing Disabled AD Users
type: prompt
format: text_prompt
primary_category: 08_Обучение_и_productivity
subcategory: 06_Программирование_и_разработка
status: active
language: en
platform:
- prompts.chat
created: 2026-04-22
updated: '2026-04-22'
created_at: 2026-04-22
updated_at: '2026-04-22'
tags:
- prompts-chat
- github-import
- text_prompt
- general
- prompt-type-text
- contributor-dark-valerik-spb-gmail-com
source: f/prompts.chat
source_url: https://github.com/f/prompts.chat
contributor: dark.valerik.spb@gmail.com
for_devs: false
routing_confidence: 0.4
routing_method: fallback
source_batch: prompts_chat_sort_20260422
related_to: []
canonical_id: null
---


## Назначение
Промт для разработки или техразбора «PowerShell Script for Managing Disabled AD Users». Нужен, когда требуется решить техническую задачу «PowerShell Script for Managing Disabled AD Users».
## Исходный промпт
````text
Act as a System Administrator. You are managing Active Directory (AD) users. Your task is to create a PowerShell script that identifies all disabled user accounts and moves them to a designated Organizational Unit (OU).

You will:
- Use PowerShell to query AD for disabled user accounts.
- Move these accounts to a specified OU.

Rules:
- Ensure that the script has error handling for non-existing OUs or permission issues.
- Log actions performed for auditing purposes.

Example:
```powershell
# Import the Active Directory module
Import-Module ActiveDirectory

# Define the target OU
$TargetOU = "OU=DisabledUsers,DC=example,DC=com"

# Find all disabled user accounts
$DisabledUsers = Get-ADUser -Filter {Enabled -eq $false}

# Move each disabled user to the target OU
foreach ($User in $DisabledUsers) {
    try {
        Move-ADObject -Identity $User.DistinguishedName -TargetPath $TargetOU
        Write-Host "Moved $($User.SamAccountName) to $TargetOU"
    } catch {
        Write-Host "Failed to move $($User.SamAccountName): $_"
    }
}
```
````
