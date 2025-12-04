# Feature: Edit Category Button for Auto-Recognized Checks

## Overview
Added "Edit Category" button (✏️) to the auto-recognized check confirmation screen, allowing users to quickly correct misclassified receipts before saving.

## Changes Made

### 1. `handlers/transactions.py`
- **Modified `handle_photo()` function (lines ~250-277)**:
  - Added third button to the `confirming_auto_check` keyboard
  - Button text: "✏️ Изменить категорию"
  - Button callback: `"edit_category"`
  - Keyboard layout now has 2 buttons on row 1, 1 button on row 2

- **Added new handler `process_edit_category()` (lines ~376-398)**:
  - Triggered when user clicks "Edit Category" button
  - Retrieves transaction type from FSM data
  - Shows category selection keyboard (same as manual category choice flow)
  - Transitions FSM to `Transaction.choosing_category_after_check` state
  - Delegates further processing to existing `process_category_choice_after_check()` handler

### 2. `main.py`
- **Added import** (line ~11):
  - `process_edit_category` added to handler imports
  
- **Registered callback handler** (line ~57):
  - `dp.callback_query.register(process_edit_category, F.data == "edit_category", Transaction.confirming_auto_check, AllowedUsersFilter())`
  - Routes callback when:
    - User is in `confirming_auto_check` state
    - Callback data equals `"edit_category"`
    - User is in allowed list

## User Flow

### Before (Auto-Check Confirmation)
```
Check Photo → Auto-Categorize → Show Preview + [Confirm | Cancel]
```

### After (Auto-Check Confirmation with Edit Option)
```
Check Photo → Auto-Categorize → Show Preview + [Confirm | Cancel]
                                                     [Edit Category]
                                    ↓ (User clicks Edit)
                                  Show Category Selection
                                    ↓ (User picks category)
                                  Show Confirmation + [Confirm | Cancel]
                                    ↓ (User confirms)
                                  Save + Learn Keywords
```

## Key Properties
- **Non-Breaking**: Does not affect existing auto-check flow if edit button is not used
- **Reuses Existing Logic**: Leverages existing category selection and confirmation handlers
- **Learns Keywords**: When user confirms after editing, keywords are automatically saved (same as manual category choice flow)
- **FSM State Transition**: `confirming_auto_check` → `choosing_category_after_check` → `confirming_check`

## Testing Checklist
- [ ] Auto-recognized check with correct category: [Confirm] and [Cancel] buttons work normally
- [ ] Auto-recognized check with wrong category: [Edit Category] button shows category selection
- [ ] After selecting new category: Confirmation screen appears with keywords ready to learn
- [ ] Keywords are saved to sheet when confirming edited category

## Commit Info
- Branch: `fixup`
- Commit: `494d490`
- Message: "Add edit category button for auto-recognized checks"
