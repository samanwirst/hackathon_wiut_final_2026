The challenge
Each finalist team builds a working AI product for its track and defends it as a business case. There is no dataset and no leaderboard: you choose the problem, find the data, and prove that the product works, pays off and is hard to copy.
Choose one mode and name it on your first slide. Both are judged by the same criteria.
- Startup: an independent product with its own customers and revenue.
- Partner product: a product that runs inside a partner company. Name the unit that owns it and the process it changes.
Every team hands in three things
1. A prototype that runs end to end, live, including on an input the jury gives you.
2. A deck for the defence.
3. A repository with the code, a README to run it, and the list of data sources with their licences.
Track: Computer Vision
Partners: Toyota Royal Motors, BYD Royal Motors and Ducati.
Build a product that turns images or video into a decision or an action for the automotive business or for road safety. The user can be a dealer, a service centre, an insurer, a fleet owner, a driver or a city.
Directions are examples, not limits
- Vehicle inspection: damage and defect detection at handover, trade-in, service intake or an insurance claim; appraisal of a used vehicle from photos.
- Dealer and service operations: service-bay and stock-yard analytics, plate recognition linked to the customer record, parts identification, pre-delivery inspection.
- Driver and road safety: driver monitoring, motorcycle rider safety, dashcam analytics, road-condition mapping, traffic events that continue your elimination task.
- EV and infrastructure: charging-station occupancy and state, parking, fleet monitoring.
Engineering constraint
The product must run in real conditions. State where inference runs (edge device, server or cloud), the speed on your hardware, the cost per camera or per inspection, and how quality holds at night, in rain, and on local vehicles and plates.
Demo
All the web versions of the solutions should be deployed and be publicly available. Judges (optionally, other contestants) should be able to test it on their own laptops and/or mobile phones. It is a part of the demo and presentation, which will be graded.
Rules
No data is provided by the organisers or partners. Both tracks follow the same rules.
Allowed
- Any LLM, coding assistant, open-source model, pretrained weights, public dataset or public API. Paid services are at your own expense and must appear in your cost model.
- Data you find, collect or generate yourself, including synthetic data, with the source and the generation method declared.
- Your own elimination-stage code and public libraries, declared in the README.
Not allowed
- Faked demos: hard-coded answers, mock screens shown as working features, invented metrics.
- Real personal or confidential data: customer records, non-public bank data, faces or plates of people who did not consent.
- Work made before the final, or by people outside the team, presented as built during the final.
- Code, models or ideas of others used without attribution.
The track jury may disqualify a team for any item in the second list. A single prompt to a general-purpose model behind a UI is not forbidden, but it scores low on both technology criteria.
Deployment and code freeze
- Deploy anywhere that is publicly reachable: a hosting platform (Vercel, Netlify, Render, Railway, Hugging Face Spaces…) or your own server and domain.
- Deploy from your submitted repository — frontend and backend. If you self-host, we recommend deploying through GitHub Actions so your deployment history is recorded.
- After the deadline only redeploying the submitted commit is allowed. The organisers monitor every deployed site and report changes after the deadline to the jury. At the defence you may be asked to show your deployment history or the running version on your server.
Judging criteria
Technology decides half of the score: the two technology criteria carry 50% together.
Table
Each judge scores every criterion from 0 to 10. The result is the weighted sum, averaged over the judges. Ties are broken by the sum of the two technology criteria.
Defence
Each team has 7 minutes to present and 3 minutes for questions (Q&A). Timing is enforced without exceptions.
- After 7 minutes the presentation is stopped, mid-sentence if needed. What was not shown is not judged.
- Questions take at most 3 minutes and happen only if the jury has them. The jury may address any team member, including about code written with an LLM.
- Technical problems do not stop the clock. Keep a recorded backup of the demo.
- Recommended split of the 7 minutes: problem and user 1, live demo 2, technology 2, budget and ROI 1.5, next steps 0.5. The split is a recommendation; the total is not.