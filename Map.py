import xmltodict, json
from io import StringIO

input_var = '<?xml version="1.0" encoding="UTF-8" standalone="no"?><AcknowledgeWorkflow releaseID="2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schema.infor.com/InforOAGIS/2 http://schema.infor.com/2.5.0/InforOAGIS/BODs/Developer/AcknowledgeWorkflow.xsd" xmlns="http://schema.infor.com/InforOAGIS/2"><ApplicationArea><Sender><LogicalID>infor.engine.workflow</LogicalID><ComponentID>ION_Workflow_Engine</ComponentID></Sender><CreationDateTime>2020-06-16T10:37:12.312Z</CreationDateTime></ApplicationArea><DataArea><Acknowledge><TenantID>VRKUNNOSSAPITOOY_TST</TenantID><OriginalApplicationArea><Sender><LogicalID>infor.workflow.workflow1-bbadbb00-252c-4b90-be31-e6adafff4201</LogicalID></Sender><CreationDateTime>2020-06-16T10:37:10.866Z</CreationDateTime><BODID>process.workflow-1-1</BODID></OriginalApplicationArea><ResponseCriteria><ResponseExpression actionCode="Accepted"/></ResponseCriteria></Acknowledge><Workflow><DocumentID><ID>2</ID></DocumentID><Status><Code>Initial</Code></Status><WorkflowDefinitionCode>test_Contact_v3</WorkflowDefinitionCode></Workflow></DataArea></AcknowledgeWorkflow>'

output_var = xmltodict.parse(input_var)
output_var = json.dumps(output_var)

output_var = json.dumps(json.loads(output_var), indent=4)
print(output_var)
