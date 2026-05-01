# Azure Portal Deployment Guide - Fear & Greed Signals

## 🌐 Deploy Using Azure Portal Website (No CLI Required!)

This guide shows you how to deploy your Fear & Greed signal system using only the Azure Portal website.

**Time Required**: 30-40 minutes
**Monthly Cost**: $0 (Free tier)

---

## 📋 Prerequisites

1. ✓ Azure subscription (you already have this!)
2. ✓ Test completed locally (test_local.py passed)
3. ✓ Code ready in `FearGreedStrategy/CombineBoth/`

---

## 🚀 DEPLOYMENT STEPS

### STEP 1: Login to Azure Portal (2 minutes)

1. **Open browser** and go to: https://portal.azure.com
2. **Login** with your Azure account credentials
3. You should see the Azure Portal dashboard

---

### STEP 2: Create Function App (10 minutes)

1. **Click** the "Create a resource" button (top left or center of page)

2. **Search** for "Function App" in the search bar
   - Select "Function App" from results
   - Click "Create"

3. **Fill out the Basics tab**:

   **Project Details:**
   - **Subscription**: Select your subscription
   - **Resource Group**: Click "Create new"
     - Name: `fear-greed-rg`
     - Click OK

   **Instance Details:**
   - **Function App name**: `fear-greed-signals-YOURNAME` (must be globally unique)
     - Example: `fear-greed-signals-john`
     - If taken, try adding numbers: `fear-greed-signals-john123`
   - **Runtime stack**: `Python`
   - **Version**: `3.10` or `3.11`
   - **Region**: `East US` (or closest to you)

   **Operating System:**
   - **Operating System**: `Linux`

   **Hosting:**
   - **Plan type**: `Consumption (Serverless)` ← This is FREE tier!

4. **Click** "Review + Create" at bottom

5. **Review** your settings, then click "Create"

6. **Wait** 2-3 minutes for deployment to complete
   - You'll see a notification when done
   - Click "Go to resource" when deployment completes

---

### STEP 3: Prepare Deployment Package (5 minutes)

We need to create a ZIP file of your code.

1. **Open Windows Explorer** and navigate to:
   ```
   C:\Users\mtzal\source\repos\python\finviz\FearGreedStrategy\CombineBoth
   ```

2. **Select ALL files** in the CombineBoth folder:
   - `__init__.py`
   - `combined_signal_generator.py`
   - `function.json`
   - `host.json`
   - `requirements.txt`
   - `test_local.py`
   - `SPY` folder
   - `BTC` folder
   - All other files

3. **Right-click** on selected files → "Send to" → "Compressed (zipped) folder"
   - Name it: `function-app.zip`
   - Save on Desktop or Downloads for easy access

**IMPORTANT**: The ZIP should contain the files directly, NOT a parent folder.
- ✓ Correct: `function-app.zip` → `__init__.py`, `host.json`, etc.
- ✗ Wrong: `function-app.zip` → `CombineBoth` → `__init__.py`, etc.

If you accidentally zipped the parent folder:
1. Extract the zip
2. Open the extracted `CombineBoth` folder
3. Select all files INSIDE it
4. Create new zip from those files

---

### STEP 4: Deploy Code via Portal (5 minutes)

#### Option A: Using Advanced Tools (Kudu) - RECOMMENDED

1. **In Azure Portal**, navigate to your Function App
   - Find it in "All resources" or search for `fear-greed-signals`

2. **In left sidebar**, scroll down to "Development Tools" section
   - Click "Advanced Tools"
   - Click "Go" button
   - This opens Kudu (Azure's deployment tool)

3. **In Kudu dashboard**, click "Tools" menu (top)
   - Select "ZIP Push Deploy"

4. **Drag and drop** your `function-app.zip` file onto the page
   - OR click "Browse" and select the file
   - Wait for upload to complete (may take 2-3 minutes)
   - You'll see "Deployment successful" message

5. **Close** Kudu tab and return to Azure Portal

#### Option B: Using VS Code Extension (Alternative)

If you have VS Code installed:

1. **Install** Azure Functions extension in VS Code
   - Open VS Code Extensions (Ctrl+Shift+X)
   - Search "Azure Functions"
   - Install by Microsoft

2. **Sign in** to Azure in VS Code
   - Click Azure icon in left sidebar
   - Click "Sign in to Azure"

3. **Deploy**:
   - Right-click on `CombineBoth` folder
   - Select "Deploy to Function App"
   - Choose your subscription
   - Select `fear-greed-signals-YOURNAME`
   - Confirm deployment

---

### STEP 5: Configure Application Settings (3 minutes)

1. **In Azure Portal**, go to your Function App

2. **In left sidebar**, click "Configuration" (under Settings section)

3. **Click** "+ New application setting" button

4. **Add timezone setting**:
   - **Name**: `WEBSITE_TIME_ZONE`
   - **Value**: `Eastern Standard Time`
   - Click OK

5. **Optional: Add Python path** (if import errors occur):
   - Click "+ New application setting" again
   - **Name**: `PYTHONPATH`
   - **Value**: `/home/site/wwwroot`
   - Click OK

6. **Click "Save"** at the top
   - Click "Continue" to confirm restart

---

### STEP 6: Configure Timer Schedule (3 minutes)

Your timer is already configured in `function.json`, but let's verify:

1. **In Azure Portal**, go to your Function App

2. **In left sidebar**, click "Functions" (under Functions section)

3. You should see your function listed:
   - Name: `CombineBoth` or `TimerTrigger`
   - Type: Timer Trigger

4. **Click** on the function name

5. **In left sidebar**, click "Integration"

6. **Click** on "Timer (Timer)" under Triggers

7. **Verify schedule**:
   ```
   0 0 13,22 * * 1-5
   ```

   This means:
   - **13:00 UTC** = 8:00 AM ET (pre-market)
   - **22:00 UTC** = 5:00 PM ET (post-market)
   - **Monday-Friday only**

8. **During Daylight Saving Time** (March-November), change to:
   ```
   0 0 12,21 * * 1-5
   ```
   - **12:00 UTC** = 8:00 AM EDT
   - **21:00 UTC** = 5:00 PM EDT

9. **Click "Save"** if you made changes

---

### STEP 7: Install Dependencies (5 minutes)

Azure automatically installs dependencies from `requirements.txt`, but we can verify:

1. **Go to Function App** in portal

2. **Click "Console"** in left sidebar (under Development Tools)
   - OR use Kudu → Debug console → CMD

3. **Type these commands** in console:
   ```bash
   cd /home/site/wwwroot
   ls
   ```
   You should see your files listed.

4. **Check if dependencies installed**:
   ```bash
   python -c "import pandas; print(pandas.__version__)"
   python -c "import yfinance; print('yfinance installed')"
   python -c "import telegram; print('telegram installed')"
   ```

5. If any errors, manually trigger installation:
   ```bash
   pip install -r requirements.txt
   ```

---

### STEP 8: Test the Function (5 minutes)

#### Manual Test Run:

1. **In Azure Portal**, go to your Function App

2. **Click "Functions"** in left sidebar

3. **Click** on your function name

4. **Click "Code + Test"** in left sidebar

5. **Click "Test/Run"** button at top

6. **Click "Run"** in the right panel that appears

7. **Watch the Logs** section at bottom:
   - You should see output starting: "GENERATING COMBINED SIGNALS"
   - Signal generation for SPY, QQQ, IBIT, BTC-USD
   - "Telegram message sent successfully!"

8. **Check your Telegram** - you should receive the message!

#### View Execution Logs:

1. **Click "Monitor"** in left sidebar (under your function)

2. **Click "Logs"** tab at bottom
   - You'll see real-time execution logs

3. **Look for**:
   - ✓ Function started
   - ✓ Stock signals generated
   - ✓ Bitcoin signals generated
   - ✓ Telegram message sent
   - ✓ Function completed successfully

---

## 📊 MONITORING

### View Execution History:

1. **Go to Function App** → **Functions** → Your function

2. **Click "Monitor"** in left sidebar

3. See all executions with:
   - Timestamp
   - Status (Success/Failed)
   - Duration
   - Invocation ID

4. **Click any execution** to see detailed logs

### Enable Application Insights (Recommended):

1. **Go to Function App** main page

2. **Click "Application Insights"** in left sidebar

3. **Click "Turn on Application Insights"**
   - Create new or use existing
   - Click "Apply"

4. **View insights**:
   - Click "View Application Insights data"
   - See performance metrics, failures, dependencies

---

## 🎛️ SCHEDULE MANAGEMENT

### Change Run Times:

Want different times? Edit the schedule:

1. **Go to Function** → **Integration** → **Timer**

2. **Change Schedule** to one of these:

   **Pre-market only** (8 AM ET):
   ```
   0 0 13 * * 1-5
   ```

   **Post-market only** (5 PM ET):
   ```
   0 0 22 * * 1-5
   ```

   **Every 4 hours** (during market hours):
   ```
   0 0 13,17,21 * * 1-5
   ```

   **Once per day** (9 AM ET):
   ```
   0 0 14 * * 1-5
   ```

3. **Click "Save"**

---

## 🛠️ TROUBLESHOOTING

### Problem: Function Not Running

**Check 1: Function App Status**
- Portal → Function App → Overview
- Ensure "Status" shows "Running"
- If not, click "Start"

**Check 2: Timer Enabled**
- Portal → Functions → Your function
- Ensure it's not disabled

**Check 3: Schedule Correct**
- Portal → Function → Integration
- Verify CRON expression

### Problem: No Telegram Messages

**Check 1: View Logs**
- Portal → Function → Monitor → Logs
- Look for errors in execution logs

**Check 2: Test Locally First**
```bash
cd FearGreedStrategy/CombineBoth
python test_local.py
```
If local works but Azure doesn't, it's an Azure configuration issue.

**Check 3: Check Function Execution**
- Portal → Function → Code + Test → Test/Run
- Watch for errors in console

### Problem: Import Errors

**Solution**: Set Python path:
1. Portal → Function App → Configuration
2. Add application setting:
   - Name: `PYTHONPATH`
   - Value: `/home/site/wwwroot`
3. Save and restart

**Solution 2**: Check file structure in Kudu:
1. Portal → Function App → Advanced Tools → Go
2. Debug console → CMD
3. Navigate to /home/site/wwwroot
4. Verify SPY/EnhancedStrategy/ and BTC/ folders exist

### Problem: Timeout Errors

**Solution**: Increase timeout in `host.json`:
1. Edit locally: Change `"functionTimeout": "00:15:00"`
2. Re-upload ZIP file via Kudu

---

## 🔄 UPDATE DEPLOYMENT

When you make code changes:

1. **Edit files locally** in `CombineBoth/`

2. **Test locally**:
   ```bash
   python test_local.py
   ```

3. **Create new ZIP file** with updated files

4. **Upload via Kudu**:
   - Portal → Function App → Advanced Tools → Go
   - Tools → ZIP Push Deploy
   - Drag new ZIP file

5. **Restart Function App**:
   - Portal → Function App → Overview
   - Click "Restart" at top

Changes are live in 1-2 minutes!

---

## 🗑️ DELETE EVERYTHING

To remove all resources and stop costs:

1. **Go to Resource Groups** in Azure Portal

2. **Click** on `fear-greed-rg`

3. **Click "Delete resource group"** at top

4. **Type the resource group name** to confirm

5. **Click "Delete"**

Everything is deleted immediately.

---

## 💰 COST TRACKING

### View Current Costs:

1. **Go to** "Cost Management + Billing" in Azure Portal

2. **Click "Cost analysis"**

3. **Filter by**:
   - Resource Group: `fear-greed-rg`
   - Time range: Last 30 days

4. **Expected cost**: $0/month (stays in free tier)

### Free Tier Limits:
- 1 million executions/month
- 400,000 GB-seconds compute
- Your usage: ~60 executions/month (way under!)

---

## ✅ DEPLOYMENT CHECKLIST

- [ ] Logged into Azure Portal
- [ ] Created Function App (Consumption plan)
- [ ] Created deployment ZIP file (correct structure)
- [ ] Uploaded code via Kudu
- [ ] Set WEBSITE_TIME_ZONE = "Eastern Standard Time"
- [ ] Verified timer schedule (13:00 and 22:00 UTC)
- [ ] Ran manual test (Code + Test → Run)
- [ ] Received Telegram test message
- [ ] Checked Monitor logs for success
- [ ] Enabled Application Insights (optional)
- [ ] Set calendar reminder to check signals daily

---

## 📱 WHAT TO EXPECT

### First Scheduled Run:

Your function will automatically run at:
- **8:00 AM ET** - Before market opens (9:30 AM)
- **5:00 PM ET** - After market closes (4:00 PM)

### Telegram Message Format:

```
🚀 FEAR & GREED DAILY SIGNALS 🚀
📅 2025-11-01 08:00 ET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STOCK SIGNALS (2-3 Week Swings)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPY 🟡 HOLD
├ Price: $682.06
├ F&G Index: 58.9 (Neutral)
└ No action - wait for signal

QQQ 🟢 BUY 🔔 NEW!
├ Price: $629.07
├ F&G Index: 61.6 (Greed)
├ 🎯 Stop: $597.61 (-5%)
├ 🎯 Target: $704.56 (+12%)
├ ⏱ Max Hold: 21 days
└ 💰 Position: 50-70% of capital

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
₿ BITCOIN SIGNALS (1-2 Week Swings)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IBIT 🟡 HOLD
├ Price: $62.30
├ F&G Index: 46.9 (Fear)
└ No action - wait for signal

BTC-USD 🟡 HOLD
├ Price: $110,262
├ F&G Index: 54.0 (Neutral)
└ No action - wait for signal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SUMMARY
├ 🟢 BUY Signals: 1
├ 🔴 SELL Signals: 0
└ 🟡 HOLD Signals: 3

⚠️ RISK MANAGEMENT
├ Stocks: Max 50-70% position
├ Bitcoin: Max 30-50% position
└ Always use stop losses!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generated by Fear & Greed System
```

---

## 🎯 SUCCESS!

Your Fear & Greed signal system is now:
- ✓ Deployed on Azure
- ✓ Running automatically twice daily
- ✓ Sending Telegram notifications
- ✓ Completely FREE (Consumption plan)

**Next**: Wait for your first scheduled run at 8 AM or 5 PM ET, or run a manual test now!

---

## 📞 NEED HELP?

### Azure Portal Help:
- Click "?" icon in top right of portal
- Search for "Function App" documentation

### Check Logs:
- Portal → Function App → Monitor → Logs
- Look for specific error messages

### Test Locally:
```bash
cd FearGreedStrategy/CombineBoth
python test_local.py
```

If local test works but Azure fails:
1. Check file structure in Kudu
2. Verify PYTHONPATH setting
3. Check dependencies installed
4. Review function execution logs

---

**Ready to deploy? Start with STEP 1!** 🚀
