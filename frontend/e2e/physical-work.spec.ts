import {test,expect} from '@playwright/test';

const apiBase=process.env.FACTORY_E2E_API_BASE_URL??'http://127.0.0.1:8002';

test('edited MuJoCo world and three-item order preserve measured state',async({page,request})=>{
  test.setTimeout(420_000);
  await page.emulateMedia({reducedMotion:'reduce'});

  await page.goto('/workspace',{waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:'Edit physical world'}).click({timeout:90_000});
  await page.getByRole('button',{name:'Add box'}).click();
  await expect(page.getByText(/World version\s+1\./)).toBeVisible();
  await page.getByRole('combobox',{name:'Inspect'}).selectOption('geometry:block_1');
  await page.getByRole('spinbutton',{name:'Yaw about Z °'}).fill('35');
  await page.locator('.physical-property').filter({hasText:'Yaw about Z'}).getByRole('button',{name:'Apply'}).click();
  await expect(page.getByText(/World version\s+2\./)).toBeVisible();
  await expect(page.getByRole('spinbutton',{name:'Yaw about Z °'})).toHaveValue('35');
  await page.getByRole('button',{name:'Undo',exact:true}).click();
  await expect(page.getByText(/World version\s+3\./)).toBeVisible();
  await expect(page.getByRole('spinbutton',{name:'Yaw about Z °'})).toHaveValue('0');

  await page.goto('/lab',{waitUntil:'domcontentloaded'});
  await page.locator('.fulfillment-panel > summary').click({timeout:90_000});
  await page.getByRole('button',{name:'Create three-item order'}).click();
  await expect(page.getByRole('button',{name:'Run physical sort'})).toBeEnabled({timeout:90_000});
  await page.getByRole('button',{name:'Run physical sort'}).click();
  await expect(page.getByText(/3\s*\/\s*3\s*items physically sorted/)).toBeVisible({timeout:300_000});
  await expect(page.locator('.fulfillment-timeline li').first()).toContainText('completed');
  await expect(page.locator('.fulfillment-timeline li').nth(1)).toContainText('blocked');

  const identity=await page.evaluate(()=>({
    id:localStorage.getItem('vivacity:fulfillment-order'),
    token:localStorage.getItem('vivacity:workspace-capability'),
  }));
  expect(identity.id).toBeTruthy();
  expect(identity.token).toBeTruthy();
  const response=await request.get(`${apiBase}/v1/fulfillment/orders/${identity.id}`,
    {headers:{'X-Workspace-Token':identity.token!}});
  expect(response.status()).toBe(200);
  const order=await response.json();
  expect(order.status).toBe('sort_completed');
  expect(order.sorted_count).toBe(3);
  expect(order.metrics.cartons_sorted).toBe(3);
  expect(order.metrics.simulation_steps).toBeGreaterThan(1000);
  expect(order.events.filter((event:{kind:string})=>event.kind==='destination_arrival')).toHaveLength(3);
  expect(order.tasks.slice(1).every((task:{status:string})=>task.status==='blocked')).toBe(true);
});
