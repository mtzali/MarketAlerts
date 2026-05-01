# Azure Deployment Guide - Combined Fear & Greed Signals

## 🎯 What This Does

Automatically runs your Fear & Greed strategies on Azure and sends Telegram notifications:
- **Pre-market** (8:00 AM ET): Get signals before market opens
- **Post-market** (5:00 PM ET): Review end-of-day signals

**Tickers**: SPY, QQQ (stocks) + IBIT, BTC-USD (Bitcoin)

---

## 📋 Prerequisites

### 1. Azure Account
- Sign up at: https://azure.microsoft.com/free/
- **Free tier**: 1 million executions/month (plenty for 2x/day!)
- Credit card required but won't be charged for free tier

### 2. Software Installed
- **Python 3.9+**: Already installed ✓
- **Azure CLI**: Download from https://aka.ms/InstallAzureCLIDirect
- **Azure Functions Core Tools**: `npm install -g azure-functions-core-tools@4`

### 3. Telegram Setup
- Already configured in your code ✓
- Bot Token: Set via TELEGRAM_BOT_TOKEN_MAIN env var
- Chat ID: Set via TELEGRAM_CHAT_ID_MAIN env var

---

## 🚀 STEP-BY-STEP DEPLOYMENT

### STEP 1: Test Locally (5 minutes)

1. **Open terminal** in `FearGreedStrategy/CombineBoth/`

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Test the system**:
```bash
python test_local.py
```

4. **Check Telegram** - You should receive a message with signals!

If you see the message, proceed to Azure deployment. If not, troubleshoot first.

---

### STEP 2: Install Azure Tools (10 minutes)

1. **Install Azure CLI**:
   - Download: https://aka.ms/InstallAzureCLIDirect
   - Run installer
   - Restart terminal

2. **Verify installation**:
```bash
az --version
```

3. **Install Azure Functions Core Tools**:
```bash
npm install -g azure-functions-core-tools@4
```

4. **Verify**:
```bash
func --version
```

Should show version 4.x.x

---

### STEP 3: Login to Azure (2 minutes)

1. **Login**:
```bash
az login
```

2. Browser will open - login with your Azure account

3. **Verify**:
```bash
az account show
```

Should show your subscription info

---

### STEP 4: Create Azure Resources (10 minutes)

Run these commands **one by one** in PowerShell/Terminal:

```bash
# Set variables (change if you want different names)
$RESOURCE_GROUP = "fear-greed-rg"
$LOCATION = "eastus"
$STORAGE_NAME = "feargreedstore$(Get-Random -Minimum 1000 -Maximum 9999)"
$FUNCTION_APP = "fear-greed-signals"

# 1. Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# 2. Create storage account
az storage account create `
  --name $STORAGE_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS

# 3. Create Function App (Linux, Python 3.10)
az functionapp create `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP `
  --storage-account $STORAGE_NAME `
  --runtime python `
  --runtime-version 3.10 `
  --functions-version 4 `
  --os-type Linux `
  --consumption-plan-location $LOCATION
```

**Wait 2-3 minutes** for resources to provision.

---

### STEP 5: Prepare Deployment Files (5 minutes)

1. **Navigate to project root**:
```bash
cd C:\Users\mtzal\source\repos\python\finviz\FearGreedStrategy
```

2. **Create deployment package structure**:
Your folder structure should be:
```
CombineBoth/
├── __init__.py                 (Azure Function entry)
├── function.json               (Timer configuration)
├── host.json                   (Host settings)
├── requirements.txt            (Dependencies)
├── combined_signal_generator.py (Main logic)
├── SPY/                        (Parent folder - needed!)
│   └── EnhancedStrategy/
│       ├── enhanced_fear_greed.py
│       └── enhanced_strategies.py
└── BTC/                        (Parent folder - needed!)
    ├── btc_fear_greed.py
    └── btc_strategies.py
```

3. **Copy parent strategies** (if not already there):
```bash
# From FearGreedStrategy/CombineBoth/
cp -r ../SPY .
cp -r ../BTC .
```

---

### STEP 6: Deploy to Azure (10 minutes)

1. **Navigate to CombineBoth folder**:
```bash
cd C:\Users\mtzal\source\repos\python\finviz\FearGreedStrategy\CombineBoth
```

2. **Initialize Azure Functions** (if needed):
```bash
func init . --python
```

3. **Deploy**:
```bash
func azure functionapp publish fear-greed-signals --python
```

This will:
- Install all dependencies on Azure
- Upload your code
- Configure the timer triggers

**Wait 5-10 minutes** for first deployment (installing packages).

4. **Verify deployment**:
```bash
az functionapp list-functions --name fear-greed-signals --resource-group fear-greed-rg
```

Should show your timer-triggered function.

---

### STEP 7: Configure Time Zones (5 minutes)

Azure uses UTC by default. We need ET timezone.

1. **Set timezone**:
```bash
az functionapp config appsettings set `
  --name fear-greed-signals `
  --resource-group fear-greed-rg `
  --settings WEBSITE_TIME_ZONE="Eastern Standard Time"
```

2. **Verify**:
```bash
az functionapp config appsettings list `
  --name fear-greed-signals `
  --resource-group fear-greed-rg `
  --query "[?name=='WEBSITE_TIME_ZONE']"
```

---

### STEP 8: Verify Schedule (2 minutes)

Your function runs on this schedule (in `function.json`):
```
"schedule": "0 0 13,22 * * 1-5"
```

**Translation**:
- **13:00 UTC** = 8:00 AM ET (pre-market)
- **22:00 UTC** = 5:00 PM ET (post-market)
- **Monday-Friday** only (markets closed weekends)

**During Daylight Saving Time (DST)**, ET is UTC-4, so:
- **12:00 UTC** = 8:00 AM EDT
- **21:00 UTC** = 5:00 PM EDT

**To adjust for DST**, update `function.json`:
```json
"schedule": "0 0 12,21 * * 1-5"
```

Then redeploy:
```bash
func azure functionapp publish fear-greed-signals --python
```

---

## 🎛️ SCHEDULE OPTIONS

### Option A: Pre & Post Market (Recommended)
```json
"schedule": "0 0 13,22 * * 1-5"
```
- 8:00 AM ET (pre-market)
- 5:00 PM ET (post-market)

### Option B: Pre-Market Only
```json
"schedule": "0 0 13 * * 1-5"
```
- 8:00 AM ET only

### Option C: Post-Market Only
```json
"schedule": "0 0 22 * * 1-5"
```
- 5:00 PM ET only

### Option D: Multiple Times
```json
"schedule": "0 0 9,13,17,22 * * 1-5"
```
- 4:00 AM, 8:00 AM, 12:00 PM, 5:00 PM ET

**To change**: Edit `function.json`, then redeploy.

---

## 📊 MONITORING

### View Execution Logs

1. **Real-time logs**:
```bash
func azure functionapp logstream fear-greed-signals
```

Press Ctrl+C to exit.

2. **View in Azure Portal**:
   - Go to: https://portal.azure.com
   - Navigate to your Function App
   - Click "Monitor" → "Logs"
   - See execution history

### Check Telegram

- You should receive messages at scheduled times
- If no message, check logs for errors

---

## 🛠️ TROUBLESHOOTING

### Problem: No Telegram Messages

**Solution 1**: Check if function is running
```bash
az functionapp show --name fear-greed-signals --resource-group fear-greed-rg --query "state"
```
Should show "Running"

**Solution 2**: Check logs
```bash
func azure functionapp logstream fear-greed-signals
```
Look for errors

**Solution 3**: Test locally first
```bash
cd FearGreedStrategy/CombineBoth
python test_local.py
```
If local works but Azure doesn't, it's a deployment issue.

---

### Problem: "Module not found" errors

**Solution**: Ensure all dependencies are uploaded

1. Check `requirements.txt` is complete
2. Redeploy:
```bash
func azure functionapp publish fear-greed-signals --python --build remote
```

The `--build remote` flag forces Azure to rebuild dependencies.

---

### Problem: Timeout Errors

**Solution**: Increase timeout in `host.json`:
```json
{
  "functionTimeout": "00:15:00"
}
```

Then redeploy.

---

### Problem: Wrong Timezone

**Solution**: Set timezone explicitly
```bash
az functionapp config appsettings set `
  --name fear-greed-signals `
  --resource-group fear-greed-rg `
  --settings WEBSITE_TIME_ZONE="Eastern Standard Time"
```

---

### Problem: Deployment Fails

**Solution 1**: Check Azure CLI is logged in
```bash
az account show
```

**Solution 2**: Ensure unique function app name
If "fear-greed-signals" is taken, use:
```bash
az functionapp create --name fear-greed-signals-yourname ...
```

**Solution 3**: Delete and recreate
```bash
az group delete --name fear-greed-rg --yes
```
Then start from STEP 4.

---

## 💰 COST BREAKDOWN

### Azure Free Tier (Forever)
- **1 million executions/month**: FREE
- **400,000 GB-seconds**: FREE
- **Storage**: First 5 GB FREE

### Your Usage
- **2 runs/day** × 30 days = 60 runs/month
- **Way under free tier!**

### Expected Cost: **$0/month**

(Unless you exceed free tier limits)

---

## 🔄 UPDATE DEPLOYMENT

When you make changes to code:

1. **Edit files** in `CombineBoth/`

2. **Test locally**:
```bash
python test_local.py
```

3. **Deploy updates**:
```bash
func azure functionapp publish fear-greed-signals --python
```

That's it! Changes are live in 2-3 minutes.

---

## 🗑️ DELETE EVERYTHING

If you want to remove all Azure resources:

```bash
az group delete --name fear-greed-rg --yes
```

This deletes:
- Function App
- Storage Account
- All logs

**Cost stops immediately.**

---

## 📅 ALTERNATIVE: Manual Runs

Don't want to use Azure? Run manually:

### Option 1: Windows Task Scheduler

1. Open Task Scheduler
2. Create Task
3. Trigger: Daily at 8:00 AM and 5:00 PM
4. Action: `python C:\...\CombineBoth\combined_signal_generator.py`

### Option 2: Python Script

Create `run_scheduled.py`:
```python
import schedule
import time
from combined_signal_generator import CombinedSignalGenerator

def job():
    generator = CombinedSignalGenerator()
    generator.run()

schedule.every().day.at("08:00").do(job)
schedule.every().day.at("17:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run: `python run_scheduled.py`

Keep terminal open 24/7.

---

## ✅ POST-DEPLOYMENT CHECKLIST

- [ ] Tested locally with `test_local.py`
- [ ] Received Telegram test message
- [ ] Installed Azure CLI
- [ ] Logged into Azure
- [ ] Created resource group
- [ ] Created storage account
- [ ] Created Function App
- [ ] Deployed code successfully
- [ ] Set timezone to Eastern
- [ ] Verified schedule in `function.json`
- [ ] Checked logs for first execution
- [ ] Received first scheduled Telegram message
- [ ] Bookmarked Azure Portal link
- [ ] Set calendar reminder to check daily

---

## 📱 WHAT TO EXPECT

### Pre-Market (8:00 AM ET)
You'll receive a Telegram message like:

```
🚀 FEAR & GREED DAILY SIGNALS 🚀
📅 2025-11-01 08:00 ET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STOCK SIGNALS (2-3 Week Swings)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPY 🟢 BUY 🔔 NEW!
├ Price: $570.50
├ F&G Index: 62.3 (Greed)
├ 🎯 Stop: $541.98 (-5%)
├ 🎯 Target: $639.76 (+12%)
├ ⏱ Max Hold: 21 days
└ 💰 Position: 50-70% of capital

QQQ 🟡 HOLD
├ Price: $485.20
├ F&G Index: 52.1 (Neutral)
├ Volume: 48.3
└ Momentum: 51.2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
₿ BITCOIN SIGNALS (1-2 Week Swings)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IBIT 🟢 BUY
├ Price: $52.30
├ F&G Index: 58.7 (Greed)
├ 🎯 Stop: $47.07 (-10%)
├ 🎯 Target: $65.38 (+25%)
├ ⏱ Max Hold: 14 days
└ 💰 Position: 30-50% ⚠️

BTC-USD 🟢 BUY
├ Price: $72,340
├ F&G Index: 59.2 (Greed)
├ 🎯 Stop: $65,106 (-10%)
├ 🎯 Target: $90,425 (+25%)
├ ⏱ Max Hold: 14 days
└ 💰 Position: 30-50% ⚠️

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SUMMARY
├ 🟢 BUY Signals: 3
├ 🔴 SELL Signals: 0
└ 🟡 HOLD Signals: 1

⚠️ RISK MANAGEMENT
├ Stocks: Max 50-70% position
├ Bitcoin: Max 30-50% position
└ Always use stop losses!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generated by Fear & Greed System
```

Review and place orders before 9:30 AM market open!

---

## 🎯 NEXT STEPS

1. **Test locally** first (don't skip!)
2. **Deploy to Azure** following steps
3. **Wait for first scheduled run** (8 AM or 5 PM ET)
4. **Check Telegram** for message
5. **Review and trade** based on signals

---

## 📞 SUPPORT

### Azure Issues
- Docs: https://docs.microsoft.com/azure/azure-functions/
- Pricing: https://azure.microsoft.com/pricing/details/functions/

### Code Issues
- Check logs: `func azure functionapp logstream fear-greed-signals`
- Test locally: `python test_local.py`
- Review `combined_signals_log.csv` for history

---

**Ready to deploy? Start with STEP 1 above!** 🚀
