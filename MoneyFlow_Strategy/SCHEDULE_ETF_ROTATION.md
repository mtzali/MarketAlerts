# How to Schedule ETF Rotation (Windows Task Scheduler)

## Option 1: Run Manually (Recommended at First)

**Just double-click:**
```
run_etf_rotation.bat
```

**When to run:**
- Daily at market close (4:00-5:00 PM)
- Or anytime after market closes

**What it does:**
- Downloads latest ETF prices
- Ranks sectors by momentum
- Shows current positions
- Recommends actions (if needed)
- Sends Telegram report

---

## Option 2: Schedule to Run Automatically (Advanced)

### Step 1: Open Task Scheduler

1. Press `Windows Key + R`
2. Type: `taskschd.msc`
3. Press Enter

### Step 2: Create New Task

1. Click **"Create Task"** (not "Create Basic Task")
2. **General Tab:**
   - Name: `ETF Rotation Daily Report`
   - Description: `Daily ETF rotation recommendations`
   - ✅ Check "Run whether user is logged on or not"
   - ✅ Check "Run with highest privileges"

### Step 3: Set Trigger

1. Go to **"Triggers"** tab
2. Click **"New"**
3. Set:
   - Begin the task: **On a schedule**
   - Settings: **Daily**
   - Start: **4:30 PM** (after market close)
   - Recur every: **1 days**
   - ✅ Enabled
4. Click **OK**

### Step 4: Set Action

1. Go to **"Actions"** tab
2. Click **"New"**
3. Set:
   - Action: **Start a program**
   - Program/script:
     ```
     C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy\run_etf_rotation.bat
     ```
   - Start in (optional):
     ```
     C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy
     ```
4. Click **OK**

### Step 5: Configure Settings

1. Go to **"Settings"** tab
2. Configure:
   - ✅ Allow task to be run on demand
   - ✅ Run task as soon as possible after scheduled start is missed
   - ✅ If task fails, restart every: **5 minutes** (try **3 times**)
   - Stop the task if runs longer than: **10 minutes**
3. Click **OK**

### Step 6: Test

1. Find your task in Task Scheduler
2. Right-click → **"Run"**
3. Verify it works

---

## Recommended Schedule

### If Running Both Systems:

**Daily Reports (unified):**
- Time: **4:30 PM** weekdays
- Script: `run_daily_report.bat`
- Purpose: Market sentiment, stock ideas, COT (Fridays)

**ETF Rotation:**
- Time: **4:45 PM** weekdays
- Script: `run_etf_rotation.bat`
- Purpose: ETF rankings and rotation signals

### If Running Only ETF Rotation:

**ETF Rotation:**
- Time: **4:30 PM** weekdays
- Script: `run_etf_rotation.bat`
- Purpose: Simple ETF strategy

---

## Important Notes

### About Prompts

**The script will prompt you for rebalancing.**

If running automatically via Task Scheduler:
- The prompt won't work (no user interaction)
- Script will just generate report
- You'll see rebalance recommendation in Telegram
- **Manually run the script when you want to rebalance**

**Solution:**
1. Let Task Scheduler run daily for reports
2. When Telegram says "REBALANCE NEEDED"
3. Manually run `run_etf_rotation.bat`
4. Type `yes` when prompted

### Handling Rebalances

**Option A (Recommended):**
- Schedule runs daily for monitoring
- Manually execute rebalances when prompted
- This gives you control

**Option B (Fully Automated):**
- Modify script to auto-rebalance without prompt
- Edit `daily_etf_rotation.py` line 479:
  ```python
  # Original (prompts user):
  user_input = input("\nDo you want to execute rebalance? (yes/no): ").strip().lower()

  # Auto-rebalance (no prompt):
  user_input = 'yes'  # Always rebalance when recommended
  ```
- ⚠️ Use with caution - no manual oversight!

---

## Checking if Task is Running

### View in Task Scheduler

1. Open Task Scheduler
2. Find **"ETF Rotation Daily Report"**
3. Check **"Last Run Result"** - should be **"0x0"** (success)
4. Check **"Last Run Time"** - should be recent

### Check Output Files

1. Look for `etf_rotation_positions.json` - should update daily
2. Check Telegram - should receive daily report

### Manual Test

Run manually:
```cmd
cd C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy
run_etf_rotation.bat
```

---

## Troubleshooting

### Task shows "Could not start (0x1)"
**Fix:**
- Check path in Action is correct
- Use full absolute paths
- Remove quotes around path if present

### Task runs but no output
**Fix:**
- Task Scheduler may hide output
- Check `etf_rotation_positions.json` modification time
- Check Telegram messages
- Run batch file manually to see errors

### Python not found
**Fix:**
Add Python to system PATH or use full path:
```
C:\Users\mtzal\AppData\Local\Programs\Python\Python312\python.exe
```

### Task runs but errors
**Fix:**
1. Check error in Task Scheduler → History tab
2. Run manually to see actual error
3. Check Python packages installed
4. Verify internet connection

---

## Alternative: Simple Windows Shortcut

Instead of Task Scheduler, create a shortcut:

1. Right-click `run_etf_rotation.bat`
2. **"Send to"** → **"Desktop (create shortcut)"**
3. Double-click shortcut daily at 4:30 PM

**Pros:**
- Simple, visible, manual control
- See output immediately
- Can interact with prompts

**Cons:**
- You must remember to run it
- No automation

---

## My Recommendation

**Start with manual runs:**
1. Use desktop shortcut
2. Run daily after market close
3. Get comfortable with the process
4. Understand the reports

**After 2-4 weeks:**
1. Set up Task Scheduler for daily monitoring
2. Still manually execute rebalances
3. Check Telegram for signals

**Never:**
- Fully automate rebalancing without understanding
- Set and forget without monitoring
- Ignore stop loss alerts

---

## Sample Task Scheduler XML (Advanced)

Save this as `ETF_Rotation_Task.xml` and import:

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Daily ETF rotation recommendations</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2025-11-16T16:30:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy\run_etf_rotation.bat</Command>
      <WorkingDirectory>C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

To import:
1. Open Task Scheduler
2. **Action** → **Import Task**
3. Select `ETF_Rotation_Task.xml`
4. Adjust paths if needed
5. Click OK

---

## Summary

**Quick Start:**
```
1. Double-click run_etf_rotation.bat daily
2. Check Telegram for report
3. Rebalance when prompted monthly
```

**Automated:**
```
1. Set up Task Scheduler (4:30 PM daily)
2. Monitor Telegram reports
3. Manually run batch file to rebalance when needed
```

**Files Created:**
- `run_etf_rotation.bat` - Main batch file
- `etf_rotation_positions.json` - Auto-created position tracker

That's it! Simple and effective.
