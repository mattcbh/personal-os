-- Read Today list from Things 3 and output as JSON
-- Usage: osascript read_today.applescript

on escapeJSON(theText)
    if theText is missing value then return ""
    set theText to theText as text
    set output to ""
    repeat with i from 1 to length of theText
        set c to character i of theText
        if c is "\"" then
            set output to output & "\\\""
        else if c is "\\" then
            set output to output & "\\\\"
        else if c is (ASCII character 10) then
            set output to output & "\\n"
        else if c is (ASCII character 13) then
            set output to output & "\\n"
        else if c is (ASCII character 9) then
            set output to output & "\\t"
        else
            set output to output & c
        end if
    end repeat
    return output
end escapeJSON

on formatDate(theDate)
    if theDate is missing value then return ""
    set y to year of theDate
    set m to month of theDate as integer
    set d to day of theDate
    set mStr to text -2 thru -1 of ("0" & m)
    set dStr to text -2 thru -1 of ("0" & d)
    return (y as text) & "-" & mStr & "-" & dStr
end formatDate

tell application "Things3"
    set todayToDos to to dos of list "Today"
    set jsonOutput to "["
    set isFirst to true

    repeat with toDo in todayToDos
        if not isFirst then
            set jsonOutput to jsonOutput & ","
        end if
        set isFirst to false

        set taskID to id of toDo
        set taskName to name of toDo
        set taskNotes to notes of toDo
        set taskStatus to status of toDo

        -- Get when date (activation date / scheduled date)
        set taskWhenDate to ""
        try
            set whenDate to activation date of toDo
            if whenDate is not missing value then
                set taskWhenDate to my formatDate(whenDate)
            end if
        end try

        -- Get tags
        set taskTags to ""
        try
            set tagList to tag names of toDo
            if tagList is not missing value and tagList is not "" then
                set taskTags to tagList
            end if
        end try

        -- Get project name if task is in a project
        set projectName to ""
        try
            set proj to project of toDo
            if proj is not missing value then
                set projectName to name of proj
            end if
        end try

        -- Get area name if task is in an area
        set areaName to ""
        try
            set ar to area of toDo
            if ar is not missing value then
                set areaName to name of ar
            end if
        end try

        -- Determine completion status
        set isCompleted to "false"
        if taskStatus is completed then
            set isCompleted to "true"
        end if

        set jsonOutput to jsonOutput & "{" & ¬
            "\"id\":\"" & taskID & "\"," & ¬
            "\"name\":\"" & my escapeJSON(taskName) & "\"," & ¬
            "\"notes\":\"" & my escapeJSON(taskNotes) & "\"," & ¬
            "\"when_date\":\"" & taskWhenDate & "\"," & ¬
            "\"tags\":\"" & my escapeJSON(taskTags) & "\"," & ¬
            "\"project\":\"" & my escapeJSON(projectName) & "\"," & ¬
            "\"area\":\"" & my escapeJSON(areaName) & "\"," & ¬
            "\"completed\":" & isCompleted & ¬
            "}"
    end repeat

    set jsonOutput to jsonOutput & "]"
    return jsonOutput
end tell
