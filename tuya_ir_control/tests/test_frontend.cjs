const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/../rootfs/app/index.html','utf8');
let script=html.split('<script>')[1].split('</script>')[0];
script=script.slice(0,script.lastIndexOf("setInterval(()=>{if($('#modal')"));
const nodes=new Map(),sent=[];
function node(s){if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'24',isConnected:true,classList:{add(){},remove(){},contains(){return true}},addEventListener(){},dataset:{},focus(){}});return nodes.get(s)}
const buttons=[{dataset:{acStep:'-1'}},{dataset:{acStep:'1'}},{dataset:{}}];
const context={document:{querySelector:node,querySelectorAll:s=>s==='[data-ac-step],[data-ac-send]'?buttons:[],addEventListener(){}},window:{},setTimeout(){},clearInterval(){},setInterval(){},console,fetch:async()=>({json:async()=>({ok:true,data:{temperature:24,attributes:{}}})})};
vm.createContext(context);vm.runInContext(script,context);
context.sent=sent;vm.runInContext("post=async(path,data)=>{sent.push({path,data});return true};notice=()=>{}",context);
(async()=>{
 assert(vm.runInContext("acPanel('ac')",context).includes('aria-label="Aumentar temperatura"'));
 vm.runInContext("openAC({remote_id:'ac',remote_name:'Ar teste'})",context);
 await new Promise(resolve=>setImmediate(resolve));
 assert(node('#dialog').innerHTML.includes('acTemperature'));
 assert(!node('#dialog').innerHTML.includes('<b>22 °C</b>'));
 await buttons[1].onclick();assert.equal(sent.at(-1).data.value,25);
 await buttons[0].onclick();assert.equal(sent.at(-1).data.value,24);
 node('#acTemperature').value='30';const before=sent.length;await buttons[1].onclick();assert.equal(sent.length,before);
 vm.runInContext("state.controls=[{id:'custom',name:'Ar <teste>',type:'Ar-condicionado',protocol:'ac_structured',remote_id:'ac',keys:[]}];openCustom('custom')",context);
 assert(node('#dialog').innerHTML.includes('acTemperature'));assert(node('#dialog').innerHTML.includes('&lt;teste&gt;'));
 console.log('Frontend: catálogo e personalizado com −/+, temperatura inteira e limites verificados.');
})().catch(e=>{console.error(e);process.exitCode=1});
