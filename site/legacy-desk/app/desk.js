const $ = id => document.getElementById(id);
let lines = [], products = [];
const api = async (path, options={}) => {
  const response = await fetch('/api' + path, {headers:{'Content-Type':'application/json'}, ...options});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || response.statusText);
  return result;
};
const post = (path, body={}) => api(path,{method:'POST',body:JSON.stringify(body)});
const say = (text,error=false) => { $('feedback').textContent=text; $('feedback').className=error?'error':''; };
const money = n => 'SGD ' + n;
const cell = (row,text) => { const e=document.createElement('td'); e.textContent=text; row.append(e); return e; };
function renderLines() {
  $('draft-lines').replaceChildren();
  lines.forEach((line,index)=>{
    const row=document.createElement('tr');
    cell(row,line.productCode);cell(row,line.qty);cell(row,money(line.unitPrice));
    const action=cell(row,'');const remove=document.createElement('button');remove.textContent='Remove';
    remove.type='button';remove.onclick=()=>{lines.splice(index,1);renderLines();};
    action.append(remove);$('draft-lines').append(row);
  });
}
async function loadCustomers() {
  const chosen=$('customer-select').value;
  const list=await api('/customers?q='+encodeURIComponent($('customer-search').value));
  $('customer-select').replaceChildren();
  list.forEach(customer=>{const option=document.createElement('option');option.value=customer.id;option.textContent=customer.name+' · Tier '+customer.tier;$('customer-select').append(option);});
  if (list.some(c=>String(c.id)===chosen)) $('customer-select').value=chosen;
}
async function loadInvoices() {
  const list=await api('/invoices?q='+encodeURIComponent($('invoice-search').value));
  $('invoice-history').replaceChildren();
  list.forEach(inv=>{
    const row=document.createElement('tr');
    cell(row,inv.invoiceNo);cell(row,inv.customerName);cell(row,inv.invoiceDate);cell(row,money(inv.total));
    const action=cell(row,'');const button=document.createElement('button');button.textContent='View';button.type='button';
    button.onclick=()=>showInvoice(inv.id);action.append(button);$('invoice-history').append(row);
  });
}
async function showInvoice(id) {
  try {
    const inv=await api('/invoices/'+id);
    $('invoice-detail').textContent=inv.invoiceNo+' · '+inv.customerName+' · '+inv.invoiceDate+'\n'+
      inv.lines.map(l=>l.productCode+'  '+l.qty+' × '+l.unitPrice+' = '+l.lineNet).join('\n')+
      '\nSubtotal '+inv.subtotal+'  GST '+inv.gst+'  Total '+inv.total;
    $('credit-invoice').value=id;
  } catch(e) {say(e.message,true);}
}
async function loadCredits() {
  const [requests,notes]=await Promise.all([api('/credit-requests'),api('/credit-notes')]);
  $('credit-requests').replaceChildren();$('credit-notes').replaceChildren();
  requests.forEach(x=>{const li=document.createElement('li');li.textContent='#'+x.id+' · invoice '+x.invoiceId+' · '+money(x.amountNet)+' · '+x.status;$('credit-requests').append(li);});
  notes.forEach(x=>{const li=document.createElement('li');li.textContent=x.creditNoteNo+' · invoice '+x.invoiceId+' · '+money(x.total);$('credit-notes').append(li);});
}
function draft() { return {customerId:Number($('customer-select').value),lines}; }
async function act(work,done) {try {await work();say(done);}catch(e){say(e.message,true);} }
$('customer-search').addEventListener('input',()=>act(loadCustomers,'Customer list updated.'));
$('invoice-search').addEventListener('input',()=>act(loadInvoices,'Invoice list updated.'));
$('product-select').addEventListener('change',()=>{
  const p=products.find(p=>p.code===$('product-select').value);
  if(p) $('price-input').value=p.unitPrice;
});
$('add-line').onclick=()=>{
  const qty=Number($('quantity-input').value),price=$('price-input').value;
  if(!Number.isInteger(qty)||qty<1||qty>10000||!price||Number(price)<=0){say('Enter a valid quantity and price.',true);return;}
  lines.push({productCode:$('product-select').value,qty,unitPrice:price});renderLines();say('Line added.');
};
$('preview-invoice').onclick=()=>act(async()=>{
  const result=await post('/invoices/preview',draft());
  $('preview-body').textContent=result.customerName+' · '+result.lines.length+' line(s) · subtotal '+money(result.subtotal)+' · GST '+money(result.gst);
  $('preview-total').textContent=money(result.total);
},'Preview calculated.');
$('save-invoice').onclick=()=>act(async()=>{
  const result=await post('/invoices',draft());lines=[];renderLines();await loadInvoices();await showInvoice(result.id);
  $('preview-body').textContent='Saved as '+result.invoiceNo;
  $('preview-total').textContent=money(result.total);
},'Invoice saved.');
$('create-credit-request').onclick=()=>act(async()=>{
  await post('/credit-requests',{invoiceId:Number($('credit-invoice').value),amountNet:$('credit-amount').value,reason:$('credit-reason').value});
  await loadCredits();
},'Approved credit request created.');
$('run-invoice-job').onclick=()=>act(async()=>{const r=await post('/jobs/invoices');await loadInvoices();say('Invoice job created '+r.created+' invoice(s).');},'Invoice job finished.');
$('run-credit-job').onclick=()=>act(async()=>{const r=await post('/jobs/credit-notes');await loadCredits();say('Credit job created '+r.created+' note(s).');},'Credit job finished.');
$('monthly-report').onclick=()=>act(async()=>{$('report-output').textContent=JSON.stringify(await api('/reports/monthly?month='+encodeURIComponent($('report-month').value)),null,2);},'Monthly report loaded.');
$('annual-gst-report').onclick=()=>act(async()=>{$('report-output').textContent=JSON.stringify(await api('/reports/gst?year='+encodeURIComponent($('report-year').value)),null,2);},'Annual GST report loaded.');
async function boot() {
  await loadCustomers();products=await api('/products');
  products.forEach(p=>{const option=document.createElement('option');option.value=p.code;option.textContent=p.description+' · '+p.code;$('product-select').append(option);});
  $('product-select').dispatchEvent(new Event('change'));
  await Promise.all([loadInvoices(),loadCredits()]);
}
boot().catch(e=>say(e.message,true));
