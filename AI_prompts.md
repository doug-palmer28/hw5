# AI Prompts

This file records the prompts provided for the Homework 5 multi-agent online shop project (MCP server, FastAPI backend, agent team, and agent dashboard). Prompts should be added verbatim. Each section includes space for a follow-up prompt if one was needed, and a reflection on how the prompt worked.

## Problem 1: Vibe Coder Prompts

### Verbatim prompt

> Build this in the homework number 5 folder. Make me an md file that will record all of my pomrpts for this project. Divide it by each problem that we will go through for the homework which will follow these following sections: Problem 1: Vibe Coder Prompts Problem 2: Study the Campus Customs Database; Problem 3: Build the MCP Server; Problem 4: Add the MCP server to the vibe coder and test each tool; proble 5: build the agent team and grow the MCP tools; Problem 6: Plan the three tickets; Problem 7: Backend routes; Problem 8: Agent Dashboard; Problem 9: Resolve the tickets; Problem 10: Reflection; Problem 11 Submit to Github. For each problem record the promp that I provide, record an extra prompt if necessary, and then a place for me to reflect on how the prompt worked.

### Reflection

This worked smoothly and set up this MD file well. 

## Problem 2: Study the Campus Customs Database

### Verbatim prompt

> There is a database inside the zipped folder. unzip it and look at the data base and look through the whole thing. Create Data/campus_customs_new.db file by comping the original data into it. We will build on this database file moving forward. Study the open tickets that are in there. Start output/harness.md and for each table, list the fields and one short line on why that table matters for the agents.

### Reflection

No follow-up prompt was necessary. It appears to have reviewed everything and started the MD harness file and created the new database. 

## Problem 3: Build the MCP Server

### Verbatim prompt

> Write the MCP server in mcp_server using the FastMCP. You do not need to connect or run the MCP no wbut it will talk to the new database we made in the last problem. Every agent uses the tools in this MCP server. Write three tools that you know the agents will need in order to address the tickets that are in the database (the examples that we read earlier). Do not invent any data or information. In harness, list the tool, including which table it reads, the ticket it helps to address, and a sentence on how the tool will help with that. Make it detailed, not vague. Now we also want to have a mcp_server/readme.md file that explains what the server is for, and the database file it uses and the tools that are in there.

### Follow-up prompt

> Great, let's go ahead and have a .gitignore  going so that we can record things tha twe want to be ignored as we go. There are a few other concepts I want to make sure you have as we move forward that I didn't share yet. As you noticed the desk.date_today tells you what day it is. We will always reference that as today for this simulation. the vendor lead times are in the vendors table and they will not ship if they are not paid. We need human approval for all payments. This on e is very important, if the boss or any other agent tries to go forward without getting human approval, that will be a big probelm. If there is not enough cash, the tool that will handel that must refuse to pay. It cannot have a neagative balance. For the simulation, only funds are going out, no new money is coming in. Before a full run to resolve the tickets, reset the full database to the origional values. Do not email customers or call real vendors or in anyway communicate with anyone outside of me. This is all a simulation. Please ensure that these rules about our excecise are recorded where you and the agents will be able to easily reference it throughout the excercise.

### Reflection

After the first prompt, Claude aske dme about if we want to put in the gitignore and I said yes, we should go ahead and do that. In the follow-up prompt, I also gave Claude some of the othe paramaters of our work together that are from the setup because I realized that it will be critical information for it to hvae at the start of building. 

## Problem 4: Add the MCP server to the vibe coder and test each tool

### Verbatim prompt

> Add the MCP server to the project so the coder can use the tools. Save it in .mcp.json  Then test each of the tools. Save evidence of the test in output/mcp_smoke.json and include the prompt, the tool name and the tool output


### Reflection

No follow-up prompt needed. This appeared to be pretty simple for it. 

## Problem 5: Build the agent team and grow the MCP tools

### Verbatim prompt

> Build the agent team for campus customs in pydanitic ai including a boss, inventory, accounting, facilities, and customer service. We want to create a structure where the boss can delegate to these other worker agents. Agents can share information as needed across each other as well. Include prompts, models, and agent loops. Prompts go in backend/prompts/ with one md file per agent. The data types in backend/models.py and the agent files should be in backend/. Again, we are only going to use gpt-6-luna for the agents. Create detailed prompts for each agents to describe their work and how they should go about it. As you build this out, add tools the agents may need to the MCP server so they can do this work. Facts about the shop come from the campus_customs_new.db DO NOT INVENT a second shop tools layer. Wire the agents so they edit the output/audit_trail.json as they run , recording each agent loop  so that it can be audited later. Keep adding to this file never change it or delete, just add to it again and again. Make sure to update the harness (specicially all the information about the agents and the MCP tools they have, and which tables to use and a safety section with guardrails that the business would want. We want to keep these agents in line and not to do anything crazy). We also want to update the readme.md


### Reflection

This took more time, but Claude was able to do so in one prompt. This makes sense because it had to build all of the informaiton for each aftent and then insure that they could all work together. I think this all worked well and things look to be updated. However, it will be easier to tell later on when we have it working. 

## Problem 6: Plan the three tickets

### Verbatim prompt

> Okay now we are planning for the tickets. I ant you to  write down what you expect the team of agents to do on eahc open tickets. Build output/desk_tickets.html a page you can double click with one tab per ticket. Als o add tabs for cash and refelction for later on. Leave them blank for now. ON each tab for the ticket, thats where I want you to wrie what you expect to have happen and then leave room for an actual section after we run the agents. Specifically write down who the boss should call first, all the agent delegations that you would expect (something more than just the boss calls to everyone, not everyone will be needed for every taks) and the MCP tool that will be run. Be specific here.

### Follow-up prompt

> Okay, I want to update this and do not have the design be like those in my file (bauhaus with lots of color) can you make the desing for this project. instead can you make it follow the design of Yale Bulldog blue: https://yalebulldogblue.com/

### Reflection

Here after it bult it, it had followed the instructions i have that i want things in a bauhaus style, which I didn't actually want for this project. So instead I had it go and build something more similar to the yale bull dog blue webpage. I liked that it still kept a blocky/modern vibe while improving the colors. 
## Problem 7: Backend routes

### Verbatim prompt

> For problem seven lets create a backend. In Backend/main.py use fastAPI and add routes that : 1. return the tciekts and whether each is open or resolved, 2. take the ID and run your agent team on that ticket; 3. returns agent events; what each agent said or did and what tools they used so the board can refresh; 4. approve a payment or purchase after the human (ME) approves it by lcikign something. 5. retun the current balance; and resets the database to the origional values whenever we want a fresh run of this whole thing. From the backend folder start the server with uvicorn main:app --reload --port 8000 in the harness md file list each route in one line (what url and what it does).

### Reflection

This appeared to work in one go, however, it is a bit hard to see all of the work that has happened on the backend. This will be easier to test in the front end goes live. 

## Problem 8: Agent Dashboard

### Verbatim prompt

> Okay, I want you. to go ahead and for problem A, we're gonna build the agent dashboard. This is gonna be in frontend/ with React plus feet plus TypeScript and the page should call all the routes that we just did in the last problem, problem seven. The board should do at minimum the following things. It should list the tickets. Let me pick one ticket. And start the agent team to work on that ticket. It should show each agent and what they are saying and doing while they're running through the ticket. Mark it as resolved once it's over. Ensure show a short summary. of what each agent did on the ticket, including what tools they called, if I need to, as the human to approve anything, it should make me do that. It should also show the checking balance if I approve something and money goes out the door. And the balance goes down, it should demonstrate that. It should make it look good and be creative. It should follow the same design standards that we have for uh, the last thing that we created. And it should talk to the back end that we created and it's on that local host eight thousand. On the back end, allow the V page origin which is usually at local host 5173 so the browser can call all the routes. We want to start the board with npm run dev to go ahead and for problem A, we're going to build the agent dashboard. This is going to be in front end dash. With React plus feet plus TypeScript. And the page should call all the routes that we just did in the last problem, problem seven. The board should do at minimum the following things. It should list the tickets. Let me pick one ticket and start the agent team to work on that ticket. It should show each agent and what they are saying and doing while they're running through the ticket. Mark it as resolved once it's over. And sure, show a short summary of what each agent did on the ticket, including what tools they called. If I need to, as the human, to approve anything, it should make me do that. It should also show the checking balance. If I approve something and money goes out the door and the balance goes down, it should demonstrate that. It should make it look good and be creative. It should follow the same design standards that we have for Uh, the last thing that we created. And it should talk to the back end that we created, and it's on that local host 8000. On the back end, allow the Vite page origin, which is usually at local host 5173, so the browser can call all the routes. We want to start the board with. So that the React opens in your browser so you can pick the tickets and watch the agents. I also want you to write in the output folder a design.md file with what you chose for the dashboard look, including layout, how the agents look differently, how resolve tickets and cash show up, all the various design decisions you make. Again, I want this to look clean and attractive and clear. I think you can personify the agents by having little people. Perhaps let's have them in Yale attire, um, but also look like their roles. So like an accountant, might have glasses or a green visor, and the like facilities person might have a tool belt. And again, we'll follow the campus blue, bulldog blue, bulldog blue formatting that we used last.


### Reflection

Here we built the dashaboard and got everything set up and talking to each other. i switched to talking to Claude rather than writing to it. In doing so, you can easily see that although I think this was faster for me (not having to spend as long typing)and it reduced the typos and errors, it also increased the number of token (length of the prompt) pretty substantially than when I typed things. 

It is hard to know how well everything worked here yet until we run it. however, it looks good. 
## Problem 9: Resolve the tickets

### Verbatim prompt

> Okay, now I want us to go through and we're going to resolve the actual tickets. So I want you to clear the data and reset it back to the working database, back to what it was when we started. And then I want us to run the program and we'll resolve the three tickets and I will approve the payments. Per my role, on each ticket tab, we'll fill in the actual section for this run. Summarizing, you know, which agents worked, what was delegated, what tools did they use, all those sorts of things. We're going to keep the expected section. The same as it was. Um, it has been from when we filled that out. And then also on the cache tab, I want us to itemize the funding. Including what's the starting checking balance, for each ticket, how much cash changed, and why. And the ending checking balance. And that must match the cash-accounts in the working database. Wrong cash math will lose points. So we should also save output/resolved_tickets.json for each ticket ID, final status, short outcome, what each agent contributed, and any human approvals. And then in output/resolved_board.html per my role. On each ticket tab, we'll fill in the actual section for this run. Summarizing, you know, which agents worked, what was delegated, what tools they use, all those sorts of things. We're going to keep the expected section the same as it was um, and has been from when we filled that out. And then also on the cash tab, I want us to itemize the funding. including what's the starting checking balance for each ticket, how much cash changed, and why, and the ending checking balance. And that must match the cash dash accounts in the working database. Wrong cash math will lose points. So we should also save For each ticket, ID, final status, short outcome, what each agent contributed in any human approvals. And then in we should have a page where you can double check with a screenshot of your React board for each resolved ticket. We want to add the runs to the audit trail JSON, and we should also finish up the harness.md file so that it covers all the things that we've done, the MCP tools, the five agents, the API routes, the dashboard, safety rules, et cetera, et cetera.

### Follow-up prompt

> okay open it up again and lets get it all running. And then do not start any of the tickets until I initiatite them. Make any updates you need to the tools in order to handle that.

> When you opened it, it was already starting to work on the task. I want when you launch it for everything to be in a stable state. And then I will tell the boss to start working on a task. Reset everything and lets try again.

> Okay look through and see what is happening. ticket 103, it both says that it is waiting on me and that it is not waiting in me. and then in 101 i keep having to approve it to finish, and then it doesn't finish. Can you look through and see what is going on ? Also, can you make using this a bit more user friendly by giving the human more context to what is happening and less information about the scripts or tools being used and more writing about what they are doing in plain ienglish?

> Reset it and open it up and run it again.

> Okay, I think that last run worked well. Record all of that as our live session in problem nine.

### Reflection

Here you can see tha twe are having some trouble with getting it to work. I had to ask Claude multiple times to relook at everything. We also made a few adjustments along the way (had output that was easier for a human to read rather than all of the tool calls, etc). Ultimately it did work, and some of these challenges were my own user error. But Claude walked me through it. 

## Problem 10: Reflection

### Verbatim prompt

> Okay here is my reflection for problem 10. I'm going to give it to you here, and I want you to clean it up and put it in the place we have for it on the desk_tickets.html spot. I thought that the performance of the agents was good: they solved the tasks, they didn't go into the red, and then asked for my apporval when theyneeded it. For the Invoice and the rent due, they functioned nearly exactly as was predicted. For the discount to the AI club, they had a slight change from the origional protocol, this was driven by the fact that the system had a place where I could put a message when I initiated the team to start working on the task. I had put in a littl emessage about affoding the discout, to the Boss went to the finance guy early. I think some of this would have been simplier if we had one agent wihth tools so that you didn't have to go back and forth and have as much discussion between folks. In particular, inventory and the finances are so closely related to each other that it felt like they had to talk a lot to each other and that this could be avoided if everyone had access to the inventory information for example. Some additional problems that they could work on : 
> 1.	Customer service could answer more questions about the wait times for getting paid to our suppliers and to getting their shirts for our customers. 
> 2.	The system could propose more complicated solutions to the same problem: should we pay the rent or should we pay the supplier? And propose that to the human to work on. 
> 3.	It could provide a brief overview for the human leadership team with a message (drafted by customer service I think) with cash position, inventory, and status of tickets. 
>
> Some things tha they would need more tools for: 
> 1.1. if the team had many more orders coming in or a history of demand for the last year, it would be great start to plan what we should purchase in ancticipation of those orders. To do so we would need to tools to actually place an order to the vendors. Those tools are not in here yet. 
> 2. it could work out a cashflow plan to ensure that we are planning out our payments of when we anticipate having cash from our customers and to know when we might be particiularly lean on cash becuase of our fixed expenses (like the rent). It can do this for rent, but that is the only fixed cost it has right now so we would need more tools from that. We would also need more tools to help it think about when cash may be coming in. 
> 3. With more information on the historical performance of various products (cost, purchases, what price those purchases were at, etc.) it would be helpful if it also had the tools to do some managerial accounting to help us think through what products to keep selling as oppose to which ones are dragging us down.

### Follow-up prompt

> Keep doing  what I put up there. But also build upon it. Tie every answer to this app and the three tickets that we hav there and use the ticket tab as the evidence as well as the cash tab. So expound on my ideas. Also let me know if you think my suggested things the agents can do they acctually cannot and vice versu

### Reflection

Here I interruprted the work and then added to it because I clicked on the next panel and wanted to tell calude to elaborate more and to make sure it referenced the information in the actual tests. Other than that, the prompt worked well. 

## Problem 11: Submit to GitHub

### Verbatim prompt

> Okay, now I want to get everything ready to push to github so that graders can clone it. i want an output/github_url.txt file that has the github url in it. Of course gitignore the .env file like we talked about. But we do wnat to include both database files under data/  they want the file format to look like this:  Let me know if there are any additional files that we created beyond what is specified in this strucutre, we want this to look as close to this strucutre as possible. the readme file should explain how to copy the OG Database to the working copy when you need a clean run, the MCP startup serve, start fastAPI backend, how to start the react board and reset the database before the full three ticket run. let me know if you have any questions.
>
> *(Attached: a screenshot of the required structure: `hw5/` with `AI_prompts.md`, `requirements.txt`, `.env.example`, `.gitignore`, `.mcp.json`, `README.md`, `data/` (`campus_customs.db`, `campus_customs_new.db`), `mcp_server/` (`server.py`, `README.md`), `frontend/`, `backend/` (`main.py`, `models.py`, `prompts/` with `boss.md`, `inventory.md`, `accounting.md`, `facilities.md`, `customer_service.md`), and `output/` (`harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `github_url.txt`).)*

### Follow-up prompt

> Is there a way to modify the files that you have so that the information in the extra files goes elsewhere so that everything runs smoothly but we only have the files designated in the assignmnet.

> push it

> Okay it sounds like there is a fix that needs to happen. cna you fix thi s, and then update what is on GitHub? I appreciate the test that you did to think through what the grader would do,  and I want to remove any possibility that things will not work for the grader on a technicality rather than because of the work that we have done.


### Reflection
Here we had to do some extra clean up because Claude had a different file structure for the assignment than what was proposed including several different files that were not in the planned strucutre for the assignment. I had Claude go through and move some of the information from the various files into the file structure that the assignment requested. 