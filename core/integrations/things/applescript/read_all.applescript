-- Read all lists, projects, and areas from Things 3 and output as JSON
-- Usage: osascript read_all.applescript

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

on todoToJSON(toDo)
    tell application "Things3"
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

        -- Get project name
        set projectName to ""
        try
            set proj to project of toDo
            if proj is not missing value then
                set projectName to name of proj
            end if
        end try

        -- Get area name
        set areaName to ""
        try
            set ar to area of toDo
            if ar is not missing value then
                set areaName to name of ar
            end if
        end try

        -- Completion status
        set isCompleted to "false"
        if taskStatus is completed then
            set isCompleted to "true"
        end if

        return "{" & ¬
            "\"id\":\"" & taskID & "\"," & ¬
            "\"name\":\"" & my escapeJSON(taskName) & "\"," & ¬
            "\"notes\":\"" & my escapeJSON(taskNotes) & "\"," & ¬
            "\"when_date\":\"" & taskWhenDate & "\"," & ¬
            "\"tags\":\"" & my escapeJSON(taskTags) & "\"," & ¬
            "\"project\":\"" & my escapeJSON(projectName) & "\"," & ¬
            "\"area\":\"" & my escapeJSON(areaName) & "\"," & ¬
            "\"completed\":" & isCompleted & ¬
            "}"
    end tell
end todoToJSON

on todosToJSON(todoList)
    set jsonArray to "["
    set isFirst to true
    repeat with toDo in todoList
        if not isFirst then
            set jsonArray to jsonArray & ","
        end if
        set isFirst to false
        set jsonArray to jsonArray & my todoToJSON(toDo)
    end repeat
    return jsonArray & "]"
end todosToJSON

tell application "Things3"
    -- Build complete JSON structure
    set jsonOutput to "{"

    -- Today list
    set todayToDos to to dos of list "Today"
    set jsonOutput to jsonOutput & "\"today\":" & my todosToJSON(todayToDos)

    -- Inbox list
    set inboxToDos to to dos of list "Inbox"
    set jsonOutput to jsonOutput & ",\"inbox\":" & my todosToJSON(inboxToDos)

    -- Anytime list
    set anytimeToDos to to dos of list "Anytime"
    set jsonOutput to jsonOutput & ",\"anytime\":" & my todosToJSON(anytimeToDos)

    -- Someday list
    set somedayToDos to to dos of list "Someday"
    set jsonOutput to jsonOutput & ",\"someday\":" & my todosToJSON(somedayToDos)

    -- Upcoming list
    set upcomingToDos to to dos of list "Upcoming"
    set jsonOutput to jsonOutput & ",\"upcoming\":" & my todosToJSON(upcomingToDos)

    -- Logbook (completed tasks) - limit to recent ones
    set logbookToDos to to dos of list "Logbook"
    -- Only take first 50 for performance
    if (count of logbookToDos) > 50 then
        set logbookToDos to items 1 thru 50 of logbookToDos
    end if
    set jsonOutput to jsonOutput & ",\"logbook\":" & my todosToJSON(logbookToDos)

    -- Projects
    set jsonOutput to jsonOutput & ",\"projects\":["
    set allProjects to projects
    set isFirst to true
    repeat with proj in allProjects
        -- Skip completed projects
        if status of proj is not completed then
            if not isFirst then
                set jsonOutput to jsonOutput & ","
            end if
            set isFirst to false

            set projName to name of proj
            set projID to id of proj
            set projToDos to to dos of proj

            -- Get area of project if any
            set projArea to ""
            try
                set projAreaObj to area of proj
                if projAreaObj is not missing value then
                    set projArea to name of projAreaObj
                end if
            end try

            set jsonOutput to jsonOutput & "{" & ¬
                "\"id\":\"" & projID & "\"," & ¬
                "\"name\":\"" & my escapeJSON(projName) & "\"," & ¬
                "\"area\":\"" & my escapeJSON(projArea) & "\"," & ¬
                "\"tasks\":" & my todosToJSON(projToDos) & ¬
                "}"
        end if
    end repeat
    set jsonOutput to jsonOutput & "]"

    -- Areas
    set jsonOutput to jsonOutput & ",\"areas\":["
    set allAreas to areas
    set isFirst to true
    repeat with ar in allAreas
        if not isFirst then
            set jsonOutput to jsonOutput & ","
        end if
        set isFirst to false

        set areaName to name of ar
        set areaID to id of ar

        -- Get tasks directly in the area (not in projects)
        set areaToDos to to dos of ar

        set jsonOutput to jsonOutput & "{" & ¬
            "\"id\":\"" & areaID & "\"," & ¬
            "\"name\":\"" & my escapeJSON(areaName) & "\"," & ¬
            "\"tasks\":" & my todosToJSON(areaToDos) & ¬
            "}"
    end repeat
    set jsonOutput to jsonOutput & "]"

    set jsonOutput to jsonOutput & "}"
    return jsonOutput
end tell
