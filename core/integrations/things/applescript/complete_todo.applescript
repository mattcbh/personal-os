-- Mark a to-do as completed in Things 3
-- Usage: osascript complete_todo.applescript "THINGS_ID"
-- Returns: "completed" on success, "error: message" on failure

on run argv
    set taskID to item 1 of argv

    tell application "Things3"
        try
            set toDo to to do id taskID
            set status of toDo to completed
            return "completed"
        on error errMsg
            return "error: " & errMsg
        end try
    end tell
end run
