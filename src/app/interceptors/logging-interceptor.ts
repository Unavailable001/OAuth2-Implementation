import { HttpInterceptorFn } from '@angular/common/http';

export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  
  console.log('Outgoing request:', req.url);

  return next(req);
};
