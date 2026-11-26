"""Voice contract for the inventory service; payloads are validated again on write."""
S={'type':'STRING'}


def declaration(name,description,properties=None,required=()):
    return {'name':name,'description':description,'parameters':{'type':'OBJECT','properties':properties or {},'required':list(required)}}


DECLARATIONS=[
    declaration('get_inventory','Search the shared stock database. Always use this before making stock claims. Quantities are each; unmatched stock is unknown.',{'query':S}),
    declaration('show_inventory','Open the inventory screen or a saved scan for review. Works with no project open.',{'scan_id':S}),
    declaration('scan_inventory','Photograph the desk using USB first and Pi camera fallback, then identify/count parts with Hydrogen in the background. Returns a scan ID immediately and opens review. Never adds stock automatically. Use add for NEW stock and recount for existing stock.',
                {'mode':{**S,'enum':['add','recount']},'location':S,'request_id':S}),
    declaration('get_inventory_scan','Read a scan, its detected items and numbered boxes, review revision and any errors. Do not repeatedly poll; the screen updates automatically.',{'scan_id':S},['scan_id']),
    declaration('refine_inventory_scan','Inspect one unsaved scan item more closely without increasing quantity. Default re-reads a high-resolution crop; capture_new=true takes another camera photo only after the user positions that part and asks for it. Returns immediately.',
                {'scan_id':S,'row_id':S,'expected_revision':{'type':'INTEGER'},'capture_new':{'type':'BOOLEAN'},'request_id':S},['scan_id','row_id','expected_revision']),
    declaration('get_project_stock','Read the saved parts plan joined with current stock, compatible confirmed links, reservations and shortages. Call before answering what a project has or needs.',{'project_id':S},['project_id']),
    declaration('inventory_change','Make a validated inventory change. data_json is a JSON object following the inventory instructions. Mutations are durable and retry-safe. Scan additions require explicit user review/confirmation.',
                {'operation':{**S,'enum':['add_stock','adjust_stock','edit_part','edit_lot','undo','match_requirement','reserve','edit_scan','confirm_scan','discard_scan']},
                 'data_json':S,'request_id':S},['operation','data_json']),
]
NAMES={d['name'] for d in DECLARATIONS}
READ={'get_inventory','get_inventory_scan','get_project_stock'}
INSTRUCTIONS='''
SHARED INVENTORY AND CAMERA (supersedes older statements that you have no camera):
You can scan the desk, review stock, record quantities and match inventory to project parts plans.
Use get_inventory for stock questions and get_project_stock for project availability; saved Markdown
owned/needed columns may be old notes. The database is authoritative. Missing catalogue entries mean
UNKNOWN, never zero. Camera suggestions are UNCONFIRMED until the user reviews identity and quantity.
The camera uses USB first, falling back to the Pi ribbon camera. Hydrogen runs separately from voice.
scan_inventory returns immediately; say it is scanning, never that parts were added. The review screen
updates automatically. When the user asks about results or confirms, read get_inventory_scan first.
Count each matching physical object: three identical motors add three. Multiple angles of the same
objects are evidence, not additional stock. Use recount only for an existing storage batch; choose its
lot_id. If uncertain whether these are new or already recorded objects, resolve that before saving.
Never infer ratings, exact model numbers, compatibility, functionality or battery health from appearance.
Read labels or ask for a closer photograph/user confirmation. Keep unknown specifications empty.
Use refine_inventory_scan for a closer look at one row. A new camera close-up is only of the same part,
after the user has placed it ready; it updates identity/evidence without adding another unit.
Do not merge different capacities/voltages/models. If uncertain parts can be identified by the user,
save their corrections and confirmation; otherwise leave them pending. The user can confirm a subset.
All screen controls also have pointer alternatives. show_inventory opens the whole stock list or scan.
inventory_change operations (data_json must be a JSON OBJECT):
- add_stock: {part_id,quantity,location,condition,serial}. Existing part_id comes from get_inventory.
  For a new part omit part_id and include part:{name,category,manufacturer,model,specifications:{},aliases,notes}.
  Only name is required in part. Use integer quantity>=0. Only user-confirmed facts create manual stock.
  Conditions: available, untested, faulty. Only available stock can satisfy/reserve a project requirement.
- adjust_stock: {lot_id,expected_revision,quantity,reason,project_id?}. Quantity is the NEW absolute count.
  For "use two", read current stock then subtract two; for returns add the returned count. Supply project_id
  when consuming that project's stock so its reservation is released. Refresh after conflicts; never guess.
- edit_part: {part_id,expected_revision,part:{...all current fields...}}. Preserve unrelated details.
- edit_lot: {lot_id,expected_revision,location,condition,serial}. Changes storage or condition, not quantity.
- edit_scan: {scan_id,expected_revision,row:{...complete existing row...}}. Preserve id, boxes and evidence.
  Change part details, quantity, location, part_id/lot_id as needed. Set confirmed:true ONLY when the user
  has approved that item's identity and count. Read the returned scan revision before the next edit.
  When selecting existing stock, include part_revision from get_inventory and lot_revision from the
  selected storage batch for recounts. These prevent overwriting stock changed since your review.
- confirm_scan: {scan_id,expected_revision,row_ids:[...],confirmed:true}. Only explicitly approved,
  confirmed, unsaved rows can be committed. A scan batch is saved once. Do not call merely after detection.
- discard_scan: {scan_id,expected_revision}. Saved stock remains; undo its operation to reverse it.
- undo: {operation_id}. Only recent quantity changes with no subsequent edits can be undone safely.
- match_requirement: {project_id,requirement_id,source_revision,part_id,confirmed:true}.
  Get IDs/revision from get_project_stock. Link only a known compatible catalogue part. Name resemblance
  alone is insufficient: compare model/specifications, or get user confirmation. Empty part_id unlinks.
- reserve: {project_id,requirement_id,source_revision,quantity}. Reserve an integer quantity for a linked
  requirement. Zero releases it. Never reserve without the user's request. Reservations prevent two
  projects from allocating the same units.
When creating/updating Parts list.md, use a required-parts Markdown table with Item, Quantity,
Specification, Purpose, Already owned and Still needed columns. Quantities are numbers with units,
or Unknown for estimates/unresolved amounts. The Parts tab automatically joins this table with stock.
After saving the list, get_project_stock, search inventory and match exact confirmed compatible models
where evidence permits. Ask only about uncertain matches. Existing stock notes in project files do not
automatically add to the shared inventory: reconcile them with the user to avoid duplicate stock.
Project mutations must refer to the current active project. Keep inventory edits independent of
project document edits. Only report success once the inventory tool result confirms it.
'''
